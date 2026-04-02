# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a formal verification project for ECEN 723 (Introduction to Formal Verification, Spring 2026). The project simulates a simplified traffic system with three horizontal and three vertical roads (3×3 grid of intersections) to verify safety properties around vehicle movement, collision avoidance, and traffic signal compliance.

The system is split into two independent modules that will be integrated in Phase B:
- **i-group (Infrastructure)**: Manages traffic lights and crossing decisions at intersections
- **v-group (Vehicles)**: Simulates vehicle movement and routing decisions

## Architecture

### Shared Data Model (`common_model.py`)

Both i-group and v-group use a unified data model to ensure compatibility:

- **Node**: Represents intersections (I00–I22 in a 3×3 grid) and terminals (A, B, C, D)
- **Segment**: Represents a directed road segment with 30 slots (0–29). Segments connect nodes with a direction (NORTH, SOUTH, EAST, WEST)
- **VehicleState**: Encodes a vehicle's current position (segment + slot), destination targets, and crossing intent
- **IntersectionLightState**: Tracks which direction (if any) has a green light at an intersection
- **CrossingRequest/CrossingGrant**: Manages the handshake between vehicles and infrastructure at each intersection
- **SimulationState**: Bundles all vehicles and lights at a time step

Key conventions:
- Slot 0 is at the segment start; slot 29 is at the intersection (ready to cross)
- Each direction has a single lane (no overtaking within a segment)
- One car can cross per intersection per time step
- Vehicles start from terminal A and must visit B, C, D in any order before returning to A

### i-group (`i_group_phaseA.py`)

**Role**: Simulates road infrastructure; decides which vehicle can cross each intersection per time step.

**Main class**: `InfrastructureSimulator`
- Maintains one `IntersectionController` per intersection
- Each controller tracks a starvation counter (to prevent one direction from being starved indefinitely)
- **Key methods**:
  - `step()`: Main entry point; consumes vehicle states and outputs lights, crossing grants, congestion map, and safety report
  - `get_incoming_waiting_vehicles()`: Identifies vehicles at slot 29 with crossing requests
  - `count_waiting_by_direction()`: Aggregates waiting vehicles by direction at each intersection
  - `select_one_grant()`: Arbitrates which vehicle (if any) gets to cross; only vehicles from the current green direction are eligible
  - `detect_collisions()`: Reports if two vehicles occupy the same (segment, slot)
  - `check_safety()`: Validates red-light compliance, U-turn prevention, and grant legitimacy

**Input**: Dictionary of `VehicleState` objects  
**Output**: Dictionary with `lights`, `crossing_grants`, `congestion_map`, and `safety_report`

### v-group (`v_group_phaseA.py`)

**Role**: Simulates vehicles; routes them toward their destinations and decides when to request crossings.

**Main class**: `VehicleSimulator`
- Maintains a `RoutePlanner` for simple heuristic-based route selection
- Tracks completion of tours (visiting A → B → C → D → A)
- **Key methods**:
  - `step()`: Main entry point; optionally consumes i-group output and updates vehicle states
  - `prepare_requests()`: Advances vehicles within segments; at slot 29, builds a crossing request
  - `apply_i_group_output()`: Processes lights and grants to execute crossings
  - `is_front_blocked()`: Prevents overtaking (simple lead-car rule)
  - `mark_visit_if_needed()`: Records when a vehicle reaches B, C, or D
  - `check_collision()`: Reports duplicate (segment, slot) pairs

**Input**: Optional dictionary with `lights`, `crossing_grants`, and `congestion_map` from i-group  
**Output**: Dictionary with `vehicles`, `vehicles_for_i_group` (snapshot for i-group), and `stats`

## Common Development Commands

### Running the Code

- **i-group Phase A test**: `python i_group_phaseA.py`
  - Simulates three vehicles at various segments and checks light decisions and safety metrics
- **v-group Phase A test**: `python v_group_phaseA.py`
  - Simulates two vehicles for two steps; demonstrates route planning and interaction with i-group output

### Testing Locally

- Modify `if __name__ == "__main__":` blocks in either module to test specific scenarios
- I-group example: vehicles waiting at different directions; check light selection and starvation counters
- V-group example: vehicles advancing through segments and requesting crossings; check route planning and collision detection

## Key Safety Properties to Verify

1. **No collisions**: Two vehicles cannot occupy the same (segment, slot) at the same time
2. **No red-light violations**: Only vehicles from the green direction can cross
3. **No U-turns**: Vehicles cannot immediately return to the intersection they came from
4. **No opposite-direction driving**: Vehicles follow segment directionality
5. **At most one vehicle crossing per intersection per step**: Enforced by `select_one_grant()`
6. **At most one green light per intersection**: Checked in `check_safety()`

## Phase A to Phase B Integration Points

- The two modules communicate via:
  - **i-group → v-group**: `lights` (Dict[str, Optional[str]]), `crossing_grants` (List[Dict]), `congestion_map` (Dict[str, int])
  - **v-group → i-group**: vehicle states (Dict[str, VehicleState]) with `request_crossing` and `desired_next_segment` fields
- Both modules independently track safety violations (collisions, red-light violations, etc.) for verification
- The shared `common_model.py` ensures consistent interpretation of the road graph and vehicle positions

## File Organization

```
ECEN723_Project/
├── common_model.py           # Shared data structures and road graph definition
├── i_group_phaseA.py        # Infrastructure simulator (Phase A)
├── v_group_phaseA.py        # Vehicle simulator (Phase A)
├── project_overview.md      # Problem statement and project requirements
├── ECEN723_Phase_A.md       # Phase A submission requirements
├── common_model.md          # Design documentation (Korean; describes data model)
└── CLAUDE.md                # This file
```

## Debugging Tips

- **Check segment validity**: Ensure `current_segment` is a key in the `SEGMENTS` dict before accessing
- **Verify slot bounds**: Vehicle's `current_slot` should always be in `[0, 29]`
- **Trace crossing requests**: Look for vehicles at slot 29 with `request_crossing=True`; they should appear in `build_crossing_requests()` output
- **Inspect starvation counters**: High starvation values may indicate a less busy direction is waiting; the light should eventually favor it
- **Validate transitions**: Use `is_valid_crossing_transition()` and `is_u_turn_transition()` to debug unexpected crossing denials
- **Safety report anomalies**: If `collisions` or `red_light_violations` are non-zero, trace back the offending vehicle(s) and their segment/slot history
