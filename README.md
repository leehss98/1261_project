# ECEN 723 Traffic System Simulation

Formal verification project for a simplified 3×3 grid traffic system. Vehicles depart from terminal A, visit B, C, and D in any order, and return to A. The system is split into two independent modules that communicate via a defined interface.

## Running the Code

```bash
# Run the i-group (infrastructure) demo
python i_group_phaseA.py

# Run the v-group (vehicle) demo
python v_group_phaseA.py
```

Both files have self-contained `__main__` blocks with hardcoded test scenarios that print results to stdout.

**Requirements:** Python 3.10+, no external dependencies.

---

## Road Model (`common_model.py`)

Shared by both groups. Defines the static road graph and all data structures.

**Grid layout:**

```
A -- I00 -- I01 -- I02 -- B
      |      |      |
     I10 -- I11 -- I12
      |      |      |
     I20 -- I21 -- I22
      |                   |
      D                   C
```

- **Intersections:** I00–I22 (3×3 grid, named `I[row][col]`)
- **Terminals:** A (top-left), B (bottom-left), C (bottom-right), D (bottom-right of grid)
- **Segments:** Each road between nodes is a directed segment with 30 slots (slot 0 = start, slot 29 = intersection entry)
- **Time step:** 2 seconds; a vehicle may advance one slot or stay still per step

Key data classes:

| Class | Purpose |
|---|---|
| `VehicleState` | Position (segment + slot), visit flags (B/C/D), crossing request |
| `IntersectionLightState` | Which direction (if any) is currently green |
| `CrossingRequest` | Vehicle asking to cross an intersection |
| `CrossingGrant` | Infrastructure approving/denying a crossing request |

---

## i-group — Infrastructure Simulator (`i_group_phaseA.py`)

Manages traffic lights and crossing arbitration. Receives vehicle states from the v-group and decides which vehicle (if any) may cross each intersection per time step.

### Algorithm

1. **Identify waiting vehicles** — find all vehicles at slot 29 with `request_crossing=True` whose segment ends at an intersection.
2. **Count by direction** — group waiting vehicles at each intersection by their incoming direction (N/S/E/W).
3. **Update lights** — `IntersectionController.select_green_direction()` scores each direction by `waiting_count + starvation_counter`. The highest score wins the green light. Non-winning directions with waiting vehicles increment their starvation counter; it resets to 0 when granted.
4. **Build crossing requests** — validate each request (correct slot, valid segment transition, no U-turn) and collect per-intersection.
5. **Grant one crossing** — `select_one_grant()` filters requests to those matching the green direction, then picks deterministically (alphabetical by `car_id`). At most one grant per intersection per step.
6. **Congestion map** — count stopped vehicles on segments feeding each intersection.
7. **Safety check** — verify: no simultaneous green lights, all grants align with green direction, no wrong-direction or U-turn grants, no collisions (duplicate segment+slot positions).

### Output (per step)

```python
{
    "time_step": int,
    "lights": {"I00": "east" | "north" | None, ...},   # one per intersection
    "crossing_grants": [{"intersection_id": str, "car_id": str, "granted": bool}, ...],
    "congestion_map": {"I00": int, ...},
    "safety_report": {
        "collisions": int,
        "red_light_violations": int,
        "simultaneous_green_violations": int,
        "invalid_grant_violations": int,
        "wrong_direction_violations": int,
        "u_turn_violations": int,
    }
}
```

### Safety properties verified by i-group

- No two vehicles in the same (segment, slot)
- No grant issued to a vehicle not in the green direction
- No grant for a wrong-direction or U-turn transition
- At most one green light per intersection at any time

---

## v-group — Vehicle Simulator (`v_group_phaseA.py`)

Simulates vehicle movement and routing decisions. Consumes i-group output to execute intersection crossings.

### Algorithm

Each `step()` call does two phases:

**Phase 1 — `prepare_requests()`**: advance vehicles and build crossing intents for i-group.
1. For each vehicle, check if the front slot in the same segment is occupied (`is_front_blocked()`). If blocked, stay.
2. If not at last slot: advance one slot (`move_inside_segment()`).
3. If at last slot and the next node is a terminal (A/B/C/D): record the visit and immediately enter the outgoing segment (`advance_from_terminal()`).
4. If at last slot and next node is an intersection: choose a next segment via `RoutePlanner` and set `request_crossing=True`.
5. Run collision check.

**Phase 2 — `apply_i_group_output()`**: apply intersection results.
1. For each vehicle with `request_crossing=True` heading to an intersection, check if it has a grant in the i-group response.
2. If granted: validate the transition (no wrong direction, no U-turn), check that the light matches, then move the vehicle to slot 0 of the new segment.
3. If not granted: vehicle stays stopped at slot 29.
4. Mark visits at terminals; restart any vehicle that completed a full tour (A→B→C→D→A).
5. Run collision check again.

### Route planning (`RoutePlanner`)

- `choose_next_segment()` filters candidate outgoing segments to those passing `is_valid_crossing_transition` and not a U-turn.
- `estimate_cost()` scores each candidate by Manhattan distance on the grid (using node IDs) plus congestion penalty from the map provided by i-group.
- The lowest-cost valid segment is selected.

### Output (per step)

```python
{
    "time_step": int,
    "vehicles": {"car_1": {snapshot}, ...},         # state after full step
    "vehicles_for_i_group": {"car_1": {snapshot}, ...},  # state sent to i-group
    "stats": {
        "completed_tours": int,
        "red_light_violations": int,
        "collisions": int,
        "illegal_direction_violations": int,
        "u_turn_violations": int,
    }
}
```

### Safety properties verified by v-group

- No two vehicles in the same (segment, slot)
- No crossing when light direction does not match vehicle direction
- No illegal segment transitions (direction constraint)
- No U-turn crossings

---

## Phase A / B / C Integration

The two modules communicate through these dictionaries each step:

| Direction | Data |
|---|---|
| v-group → i-group | `Dict[str, VehicleState]` (positions, crossing requests) |
| i-group → v-group | `lights`, `crossing_grants`, `congestion_map` |

Both groups independently compute safety violations; their counts should match for collisions, red-light violations, wrong-direction violations, and U-turns.
