# ECEN 723 Spring 2026: Project Phase A Report

**Team ID:** _17_
**Group:** i-group & v-group
**Members:** _Hyunsoo Lee, Joonhyun Choi, Vishnu Rajagopal, Stephen Muttathil_
**Date:** April 3, 2026

---

## 1. Code Structure

The implementation is organized into **three files**, cleanly separating shared state from each group's logic:

| File | Role |
|---|---|
| `common_model.py` | Shared data structures, road graph, and transition predicates |
| `i_group_phaseA.py` | Infrastructure simulator: light arbitration and intersection access control |
| `v_group_phaseA.py` | Vehicle simulator: movement, routing, and tour completion |

Each road between two nodes is modeled as **two independent directed segments** (e.g., `I00_to_I01` EAST and `I01_to_I00` WEST), with **slot 0** at the entry and **slot 29** at the intersection approach. The system advances in discrete **time steps**, where each step corresponds to a synchronized state transition across all vehicles and intersections.

---

## 2. Shared Data Model (`common_model.py`)

### Key Data Classes

| Class | Purpose |
|---|---|
| `VehicleState` | Encodes the full state of a vehicle: position (`segment` + `slot`), visit flags (B/C/D), and pending crossing intent |
| `IntersectionLightState` | Records which direction (if any) currently holds the green light at an intersection |
| `CrossingRequest` | A vehicle's **wait** on the intersection semaphore; declares intent to enter the critical section |
| `CrossingGrant` | The infrastructure's **signal**; releases the semaphore for exactly one vehicle per intersection per step |
| `Segment` | A directed road segment with `from_node`, `to_node`, `direction`, and `length_slots` |

### Transition Predicates

Three shared predicates enforce movement legality and are evaluated by both groups independently:

- **`is_valid_crossing_transition`**: outgoing segment must originate at the node where the incoming segment terminates; violations indicate an illegal state transition
- **`is_u_turn_transition`**: outgoing segment must not return to the node the vehicle came from; enforces the no-U-turn invariant
- **`is_right_turn_transition`**: outgoing direction must not be a right turn of the incoming direction (EAST→SOUTH, SOUTH→WEST, WEST→NORTH, NORTH→EAST); enforces the no-right-turn invariant

---

## 3. i-group: Infrastructure Simulator

### 3.1 Architecture

The i-group is built around two classes:

- **`IntersectionController`**: one instance per intersection; owns the light state and a per-direction **starvation counter** that tracks how long each direction has been denied access, ensuring the fairness property
- **`InfrastructureSimulator`**: the top-level coordinator; drives the per-step pipeline and accumulates a `SafetyReport` of all observed invariant violations

### 3.2 Algorithm

Each call to `step(vehicles)` executes the following pipeline:

**Step 1: Identify waiting processes**
`get_incoming_waiting_vehicles()` collects all vehicles blocked at **slot 29** with `request_crossing = True`; these are processes waiting to acquire their intersection's semaphore.

**Step 2: Update the guard condition**
For each intersection, `count_waiting_by_direction()` groups blocked vehicles by direction. `select_green_direction()` evaluates the guard condition using:

```
score(direction) = waiting_count(direction) + starvation_counter(direction)
```

The direction with the highest score is granted the green light. Non-winning directions with waiting vehicles increment their starvation counter; the winner's counter resets to 0. This scoring function guarantees the **starvation-freedom** property: no direction can be deferred indefinitely.

**Step 3: Validate and build crossing requests**
`build_crossing_requests()` validates each vehicle's request against all three transition predicates. Only requests that satisfy every predicate proceed; violations are logged immediately to the safety report.

**Step 4: Acquire the semaphore**
`select_one_grant()` filters valid requests to those satisfying the current guard condition (matching the green direction) and issues exactly **one grant** (a binary semaphore signal) per intersection. Ties are broken deterministically by `car_id` (lexicographic order), ensuring **deterministic arbitration**.

**Step 5: Compute congestion map**
Counts vehicles with `stopped = True` on segments feeding each intersection; a measure of system load used by the v-group's decision procedure.

**Step 6: Verify safety invariants**
`check_safety()` audits all active invariants and appends any violations to the `SafetyReport`.

### 3.3 Output (per step)

```python
{
    "time_step": int,
    "lights": {"I00": "east" | "north" | "south" | "west" | None, ...},
    "crossing_grants": [{"intersection_id": str, "car_id": str, "granted": bool}, ...],
    "congestion_map": {"I00": int, ...},
    "safety_report": {
        "collisions": int,
        "red_light_violations": int,
        "simultaneous_green_violations": int,
        "invalid_grant_violations": int,
        "wrong_direction_violations": int,
        "u_turn_violations": int,
        "right_turn_violations": int,
    }
}
```

### 3.4 Safety Invariants Verified

| Invariant | Mechanism |
|---|---|
| Mutual exclusion: no two vehicles share a (segment, slot) | `detect_collisions()` scans all position pairs each step |
| No red-light violation: only green-direction vehicles may cross | `check_safety()` verifies every grant aligns with the active guard condition |
| At most one green direction per intersection | Checked across all controllers; violation indicates a simultaneous-access fault |
| At most one crossing per intersection per step | `select_one_grant()` issues at most one semaphore signal per intersection |
| No U-turn state transition | `validate_request()` evaluates `is_u_turn_transition()` |
| No right-turn state transition | `validate_request()` evaluates `is_right_turn_transition()` |
| No illegal segment transition | `validate_request()` evaluates `is_valid_crossing_transition()` |

---

## 4. v-group: Vehicle Simulator

### 4.1 Architecture

The v-group is built around two classes:

- **`RoutePlanner`**: a stateless decision procedure; selects the next segment given current position, target node, and the congestion map
- **`VehicleSimulator`**: maintains the global vehicle state; advances the system by one time step per call and independently tracks all invariant violations

### 4.2 Algorithm

Each call to `step(i_group_output)` executes in **two atomic phases**, mirroring a two-phase synchronization protocol:

**Phase 1: `prepare_requests(congestion_map)`**

For each vehicle:
1. **Blocking predicate** (`is_front_blocked()`): if the nearest vehicle ahead in the same segment is within **15 slots** (0.5 mile), the process blocks and clears its pending request.
2. **Internal state transition**: if not at slot 29, advance one slot.
3. **Terminal node**: record the visit and immediately execute the next segment transition chosen by the decision procedure.
4. **Intersection approach** (slot 29): invoke `build_crossing_request()`; the decision procedure selects a next segment and the vehicle issues a **wait** on the intersection semaphore by setting `request_crossing = True`.

A collision check (mutual exclusion audit) is run after all vehicles are processed.

**Phase 2: `apply_i_group_output(lights, crossing_grants)`**

For each vehicle holding a pending semaphore wait:
1. Check whether the i-group has issued a **signal** (grant) for this vehicle.
2. **If signaled**: evaluate all three transition predicates; if all pass, execute the crossing; the vehicle transitions to slot 0 of the new segment.
3. **If not signaled**: the vehicle remains blocked at slot 29, awaiting the next arbitration cycle.

After crossings are resolved, terminal visits are recorded, completed tours are detected, and any vehicle that has satisfied the liveness condition (visited all of B, C, D, and returned to A) is reset to begin a new tour.

**Decision Procedure (Route Planning)**

`choose_next_segment()` filters all candidate segments through the three transition predicates, then ranks the remainder by:

```
cost = manhattan_distance(next_node → target_node) × 2
     + congestion_penalty(next_node)
     + base_cost (10)
```

The **lowest-cost admissible candidate** is selected. This heuristic approximates a shortest-path search and is sufficient for Phase A; a complete decision procedure is planned for Phase B.

### 4.3 Output (per step)

```python
{
    "time_step": int,
    "vehicles": {"car_id": {full state snapshot}, ...},
    "vehicles_for_i_group": {"car_id": {snapshot}, ...},
    "stats": {
        "completed_tours": int,
        "red_light_violations": int,
        "collisions": int,
        "illegal_direction_violations": int,
        "u_turn_violations": int,
        "right_turn_violations": int,
    }
}
```

### 4.4 Safety Invariants Verified

| Invariant | Mechanism |
|---|---|
| Mutual exclusion: no two vehicles share a (segment, slot) | `check_collision()` audits all position pairs after each phase |
| No red-light violation | `apply_intersection_result()` checks the guard condition against the received grant |
| No U-turn state transition | `apply_intersection_result()` evaluates `is_u_turn_transition()` |
| No right-turn state transition | `apply_intersection_result()` evaluates `is_right_turn_transition()` |
| No illegal segment transition | `apply_intersection_result()` evaluates `is_valid_crossing_transition()` |

---

## 5. i-group / v-group Integration Protocol

The two modules exchange the following signals each time step:

| Direction | Signal | Semantics |
|---|---|---|
| v-group → i-group | `Dict[str, VehicleState]` | Full system state snapshot: vehicle positions, blocking status, semaphore wait requests |
| i-group → v-group | `lights` | Active guard condition: the direction whose semaphore wait may proceed |
| i-group → v-group | `crossing_grants` | Semaphore signal: names the one vehicle per intersection that may execute its crossing |
| i-group → v-group | `congestion_map` | Load metric: stopped vehicle count per intersection, consumed by the decision procedure |

The protocol guarantees that each step is processed against a **consistent global snapshot**: the v-group freezes vehicle state before sending it to the i-group, and no crossing is executed until the i-group's semaphore signals are received and applied.

---

## 6. Design Discussion

This section documents the rationale behind key implementation decisions through the lens of how the two groups negotiated their shared protocol and resolved design trade-offs.

### Road representation

**i-group:** We need to evaluate the guard condition based on the direction a vehicle is approaching from. A single bidirectional segment object would require direction resolution at runtime on every state read.

**v-group:** Agreed. If every segment encodes exactly one direction, the decision procedure can filter candidates statically and the transition predicates remain simple boolean functions.

**Decision:** Each road is represented as two independent directed segments. Both groups share a single static segment map with no runtime ambiguity.

---

### Intersection as a critical section: the semaphore model

**v-group:** We receive the `lights` output and know which direction satisfies the guard condition. Can we allow any vehicle in that direction to execute the crossing?

**i-group:** No; if two vehicles are both blocked at slot 29 on the same green direction, both satisfy the guard condition simultaneously. Without an explicit arbitration signal, both would attempt to enter the critical section in the same step, violating mutual exclusion and producing a collision.

**v-group:** So each intersection is effectively a critical section, and the `crossing_grant` is a **binary semaphore signal**; it names the one process that acquires the resource for this step.

**i-group:** Exactly. The `lights` output is the guard condition; the grant is the semaphore signal. A vehicle issues a **wait** by setting `request_crossing = True`; the i-group responds with a **signal** for exactly one vehicle per intersection. Both groups then independently verify that no invariant was violated; the i-group checks that only the granted vehicle executed the crossing; the v-group checks that it only crossed when it held a valid signal.

**Decision:** Each intersection is modeled as a binary semaphore. The i-group controls the semaphore and issues at most one signal per step. Both groups audit the same events independently; their violation counts must match.

---

### Starvation-freedom in light selection

**v-group:** A purely queue-length-based arbitration policy can permanently favor high-traffic directions. Vehicles on low-traffic approaches would never acquire the semaphore; the system would exhibit **starvation**.

**i-group:** We address this with a starvation counter per direction. Each step a direction is denied the semaphore, its counter increments. The selection function scores each direction as `waiting_count + starvation_counter`, so a direction that has waited long enough will eventually outrank a busier one. This guarantees the **starvation-freedom** property: every waiting vehicle is eventually granted access.

**Decision:** The scoring function combines queue length with accumulated wait time. The counter resets on grant and increments otherwise, enforcing fairness without requiring a full scheduling proof at this phase.

---

### Two-phase synchronization protocol

**i-group:** We require a **consistent global snapshot** of vehicle positions before computing lights and grants. If vehicles were still transitioning when we read state, our guard condition evaluation would be based on a partially-updated system state.

**v-group:** We enforce this with a two-phase step. Phase 1 advances all vehicles within their segments and freezes the state into a snapshot; this is what we send to you. Phase 2 applies your semaphore signals to resolve intersection crossings. The two phases are never interleaved; you always observe a stable state.

**Decision:** `prepare_requests()` produces a consistent snapshot before any semaphore signal is consumed. `apply_i_group_output()` applies signals only after the snapshot has been transmitted. This mirrors a two-phase commit protocol for shared state.

---

### 15-slot observability limit

**i-group:** The specification constrains a vehicle's observable state: it can detect another vehicle ahead only within 0.5 mile (15 slots) and only if no third vehicle is between them.

**v-group:** The original blocking predicate was over-conservative; it treated any vehicle ahead in the same segment as blocking, regardless of distance. A vehicle 25 slots ahead is outside the observable range and should not affect the blocking decision.

**Decision:** `is_front_blocked()` identifies the nearest vehicle ahead in the same segment and evaluates the predicate only if the gap is at most 15 slots. This correctly models the bounded observability constraint from the specification.

---

### Deterministic arbitration for semaphore signals

**v-group:** When multiple vehicles satisfy the guard condition at the same intersection, the arbitration must be deterministic to allow reproducible verification runs.

**i-group:** We order candidates lexicographically by `car_id` and select the first. This requires no additional state, produces identical outputs for identical inputs, and makes counterexample traces fully reproducible; a property that will be important in Phase C verification.

**Decision:** Semaphore signals are awarded to the lexicographically first eligible `car_id`.

---

### Right-turn prohibition: proactive vs. defensive enforcement

**v-group:** The no-right-turn constraint is enforced proactively in the decision procedure; a right-turn segment is never admitted as a candidate. The invariant is upheld before a semaphore wait is even issued.

**i-group:** We apply a second, defensive check during request validation and in the safety audit. If a right-turn request arrives, due to a bug or an unanticipated code path, it is rejected and logged as a violation. This layered enforcement follows a **defense-in-depth** approach: the v-group prevents violations by construction; the i-group detects them if they occur.

**Decision:** Right-turn transitions are excluded from the decision procedure and independently audited by both groups' safety checkers.

---

## 7. Test Results

Three test scenarios are presented: a standalone i-group test, a standalone v-group test, and an end-to-end integrated run of both groups together. All outputs shown are actual program output.

---

### 7.1 i-group Standalone Test

**Setup:** Three vehicles across two intersections to exercise semaphore arbitration and the mid-segment exclusion rule.

- `car_1`: segment `A_to_I00`, slot 29, eastbound, requesting entry to `I00_to_I01`
- `car_2`: segment `I10_to_I11`, slot 29, eastbound, requesting entry to `I11_to_I12`
- `car_3`: segment `I01_to_I11`, slot 12, mid-segment, no semaphore wait

**Actual output (Step 1):**

```
{'time_step': 1,
 'lights': {'I00': 'east', 'I01': None, 'I02': None, 'I10': None,
            'I11': 'east', 'I12': None, 'I20': None, 'I21': None, 'I22': None},
 'crossing_grants': [
     {'intersection_id': 'I00', 'car_id': 'car_1', 'granted': True},
     {'intersection_id': 'I11', 'car_id': 'car_2', 'granted': True}
 ],
 'congestion_map': {'I00': 1, 'I01': 0, 'I02': 0, 'I10': 0,
                    'I11': 1, 'I12': 0, 'I20': 0, 'I21': 0, 'I22': 0},
 'safety_report': {
     'collisions': 0, 'red_light_violations': 0,
     'simultaneous_green_violations': 0, 'invalid_grant_violations': 0,
     'wrong_direction_violations': 0, 'u_turn_violations': 0,
     'right_turn_violations': 0
 }}
```

**Observations:**
- Guard condition is set to `east` at exactly those intersections where an eastbound vehicle is blocked at slot 29; all other lights remain `None`
- Exactly one semaphore signal is issued per active intersection; mutual exclusion holds
- `car_3` at slot 12 is correctly excluded from arbitration; the semaphore wait precondition (slot 29, `request_crossing = True`) is not satisfied
- All invariant violation counters are zero

---

### 7.2 i-group: Starvation-Freedom Test

**Setup:** Two vehicles held permanently at the same intersection from competing directions to verify that the starvation counter prevents one direction from monopolizing the semaphore.

- `car_east`: segment `I10_to_I11`, slot 29, eastbound, requesting `I11_to_I12`
- `car_north`: segment `I21_to_I11`, slot 29, northbound, requesting `I11_to_I01`

**Actual output (Steps 1-4):**

```
Step 1: light=north  grants=[{'intersection_id': 'I11', 'car_id': 'car_north', 'granted': True}]
        starvation_east=1  starvation_north=0
Step 2: light=east   grants=[{'intersection_id': 'I11', 'car_id': 'car_east',  'granted': True}]
        starvation_east=0  starvation_north=1
Step 3: light=north  grants=[{'intersection_id': 'I11', 'car_id': 'car_north', 'granted': True}]
        starvation_east=1  starvation_north=0
Step 4: light=east   grants=[{'intersection_id': 'I11', 'car_id': 'car_east',  'granted': True}]
        starvation_east=0  starvation_north=1
```

**Observations:**
- The light alternates between the two directions because equal queue lengths make the starvation counter the tiebreaker
- Each denied direction increments its counter by 1; the winning direction resets to 0
- Neither direction is ever denied for two consecutive steps; starvation-freedom holds

---

### 7.3 i-group: Illegal Transition Rejection Test

**Setup:** Three vehicles at separate intersections: one valid straight crossing, one U-turn attempt, and one right-turn attempt.

- `car_ok`: `A_to_I00`, slot 29, eastbound, requesting `I00_to_I01` (valid straight crossing)
- `car_uturn`: `I00_to_I01`, slot 29, eastbound arriving at I01, requesting `I01_to_I00` (U-turn back west)
- `car_right`: `I21_to_I11`, slot 29, northbound arriving at I11, requesting `I11_to_I12` (right turn: north to east)

**Actual output (Step 1):**

```
lights:  {'I00': 'east', 'I01': 'east', 'I11': 'north'}
grants:  [{'intersection_id': 'I00', 'car_id': 'car_ok', 'granted': True}]
safety:  {
    'collisions': 0, 'red_light_violations': 0,
    'simultaneous_green_violations': 0, 'invalid_grant_violations': 0,
    'wrong_direction_violations': 0,
    'u_turn_violations': 1, 'right_turn_violations': 1
}
```

**Observations:**
- `car_ok` receives the only grant; its crossing passes all three transition predicates
- `car_uturn` is rejected by `validate_request()` and logged as a U-turn violation; no grant is issued at I01
- `car_right` is rejected and logged as a right-turn violation; no grant is issued at I11
- Rejection occurs before `select_one_grant()`, so neither illegal vehicle ever competes for the semaphore

---

### 7.4 v-group Standalone Test

**Setup:** Two vehicles starting at `A_to_I00`, slot 0, to exercise the blocking predicate and the two-phase protocol in isolation (no i-group input).

**Actual output:**

```
Step 1 (no i-group signals):
  car_1: seg=A_to_I00  slot=1  stopped=False  req=False
  car_2: seg=A_to_I00  slot=0  stopped=True   req=False
  stats: {completed_tours:0, red_light_violations:0, collisions:0,
          illegal_direction_violations:0, u_turn_violations:0, right_turn_violations:0}

Step 2 (i-group signal: I00=east, car_1 granted):
  car_1: seg=A_to_I00  slot=2  stopped=False  req=False
  car_2: seg=A_to_I00  slot=0  stopped=True   req=False
  stats: all zeros
```

**Observations:**
- `car_1` advances: slot 0 to 1 to 2 across two steps
- `car_2` blocks at slot 0 because `car_1` is within 15 slots ahead in the same segment; the blocking predicate fires
- The grant for `car_1` at I00 in Step 2 does not produce a crossing because `car_1` has not yet reached slot 29; the signal is correctly ignored

---

### 7.5 End-to-End Integration Test

**Setup:** Both simulators running together in a closed loop for 50 steps. The v-group snapshot is forwarded to the i-group each step and the i-group lights and grants are fed back to the v-group. Two vehicles start at `A_to_I00`, slot 0.

**Selected step trace (actual output):**

```
Step 1:
  car_1: seg=A_to_I00   slot=1   stopped=False  req=False
  car_2: seg=A_to_I00   slot=0   stopped=True   req=False
  lights: {}    grants: []

Step 29:
  car_1: seg=A_to_I00   slot=29  stopped=False  req=False
  car_2: seg=A_to_I00   slot=14  stopped=False  req=False
  lights: {}    grants: []
  (car_2 is now free; car_1 is exactly 15 slots ahead, at the visibility boundary)

Step 30:  [car_1 issues semaphore wait; i-group responds with grant]
  car_1: seg=A_to_I00   slot=29  stopped=True   req=True   next=I00_to_I01
  car_2: seg=A_to_I00   slot=14  stopped=True   req=False
  lights: {'I00': 'east'}
  grants: [{'intersection_id': 'I00', 'car_id': 'car_1', 'granted': True}]

Step 31:  [car_1 executes crossing; state transition to new segment]
  car_1: seg=I00_to_I01  slot=0   stopped=False  req=False
  car_2: seg=A_to_I00    slot=14  stopped=True   req=False
  lights: {'I00': 'east'}
  grants: [{'intersection_id': 'I00', 'car_id': 'car_1', 'granted': True}]

Step 48:  [car_2 has also crossed; both vehicles on I00_to_I01]
  car_1: seg=I00_to_I01  slot=17  stopped=False  req=False
  car_2: seg=I00_to_I01  slot=0   stopped=False  req=False
  lights: {'I00': 'east'}
  grants: [{'intersection_id': 'I00', 'car_id': 'car_2', 'granted': True}]

All violation counters: zero across both groups for all 50 steps
```

**Observations:**
- `car_1` reaches slot 29 after 29 steps (one slot per step, unblocked once `car_2` falls 15 slots behind)
- At step 30, the crossing request fires and the i-group immediately sets the guard condition and issues a grant in the same step
- At step 31, `car_1` transitions atomically to slot 0 of `I00_to_I01`; one step per crossing, exactly as required
- `car_2` follows the same path 17 steps later; the i-group issues a separate independent grant
- Both groups independently count zero violations across all 50 steps; their safety audit results agree

---

## 8. Source Code

### 8.1 `common_model.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class NodeType(Enum):
    """Classify each node as either an internal intersection or an external terminal."""
    INTERSECTION = "intersection"
    TERMINAL = "terminal"


class Direction(Enum):
    """Represent the travel direction assigned to each directed road segment."""
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


@dataclass(frozen=True)
class Node:
    """Store the identifier and role of a node in the shared road graph."""
    node_id: str
    node_type: NodeType


@dataclass(frozen=True)
class Segment:
    """Describe a directed road segment between two nodes and its slot length."""
    segment_id: str
    from_node: str
    to_node: str
    direction: Direction
    length_slots: int = 30


@dataclass
class VehicleState:
    """Capture the vehicle position, visit progress, and pending crossing intent for one car."""
    car_id: str
    current_segment: str
    current_slot: int
    visited_B: bool
    visited_C: bool
    visited_D: bool
    current_target: str
    stopped: bool
    request_crossing: bool = False
    desired_next_segment: Optional[str] = None


@dataclass
class IntersectionLightState:
    """Record which direction currently has the green light at an intersection."""
    intersection_id: str
    green_direction: Optional[Direction] = None


@dataclass
class CrossingRequest:
    """Represent a vehicle request to move through an intersection into a specific outgoing segment."""
    car_id: str
    intersection_id: str
    incoming_segment: str
    outgoing_segment: str


@dataclass
class CrossingGrant:
    """Represent the infrastructure decision that approves or denies a vehicle crossing request."""
    intersection_id: str
    car_id: str
    granted: bool


@dataclass
class SimulationState:
    """Bundle the top-level simulation state shared across vehicles, lights, and time."""
    time_step: int
    vehicles: Dict[str, VehicleState]
    lights: Dict[str, IntersectionLightState]


NODES: Dict[str, Node] = {
    "I00": Node("I00", NodeType.INTERSECTION),
    "I01": Node("I01", NodeType.INTERSECTION),
    "I02": Node("I02", NodeType.INTERSECTION),
    "I10": Node("I10", NodeType.INTERSECTION),
    "I11": Node("I11", NodeType.INTERSECTION),
    "I12": Node("I12", NodeType.INTERSECTION),
    "I20": Node("I20", NodeType.INTERSECTION),
    "I21": Node("I21", NodeType.INTERSECTION),
    "I22": Node("I22", NodeType.INTERSECTION),
    "A": Node("A", NodeType.TERMINAL),
    "B": Node("B", NodeType.TERMINAL),
    "C": Node("C", NodeType.TERMINAL),
    "D": Node("D", NodeType.TERMINAL),
}


SEGMENTS: Dict[str, Segment] = {
    "I00_to_I01": Segment("I00_to_I01", "I00", "I01", Direction.EAST),
    "I01_to_I00": Segment("I01_to_I00", "I01", "I00", Direction.WEST),
    "I01_to_I02": Segment("I01_to_I02", "I01", "I02", Direction.EAST),
    "I02_to_I01": Segment("I02_to_I01", "I02", "I01", Direction.WEST),
    "I10_to_I11": Segment("I10_to_I11", "I10", "I11", Direction.EAST),
    "I11_to_I10": Segment("I11_to_I10", "I11", "I10", Direction.WEST),
    "I11_to_I12": Segment("I11_to_I12", "I11", "I12", Direction.EAST),
    "I12_to_I11": Segment("I12_to_I11", "I12", "I11", Direction.WEST),
    "I20_to_I21": Segment("I20_to_I21", "I20", "I21", Direction.EAST),
    "I21_to_I20": Segment("I21_to_I20", "I21", "I20", Direction.WEST),
    "I21_to_I22": Segment("I21_to_I22", "I21", "I22", Direction.EAST),
    "I22_to_I21": Segment("I22_to_I21", "I22", "I21", Direction.WEST),
    "I00_to_I10": Segment("I00_to_I10", "I00", "I10", Direction.SOUTH),
    "I10_to_I00": Segment("I10_to_I00", "I10", "I00", Direction.NORTH),
    "I10_to_I20": Segment("I10_to_I20", "I10", "I20", Direction.SOUTH),
    "I20_to_I10": Segment("I20_to_I10", "I20", "I10", Direction.NORTH),
    "I01_to_I11": Segment("I01_to_I11", "I01", "I11", Direction.SOUTH),
    "I11_to_I01": Segment("I11_to_I01", "I11", "I01", Direction.NORTH),
    "I11_to_I21": Segment("I11_to_I21", "I11", "I21", Direction.SOUTH),
    "I21_to_I11": Segment("I21_to_I11", "I21", "I11", Direction.NORTH),
    "I02_to_I12": Segment("I02_to_I12", "I02", "I12", Direction.SOUTH),
    "I12_to_I02": Segment("I12_to_I02", "I12", "I02", Direction.NORTH),
    "I12_to_I22": Segment("I12_to_I22", "I12", "I22", Direction.SOUTH),
    "I22_to_I12": Segment("I22_to_I12", "I22", "I12", Direction.NORTH),
    "A_to_I00": Segment("A_to_I00", "A", "I00", Direction.EAST),
    "I00_to_A": Segment("I00_to_A", "I00", "A", Direction.WEST),
    "B_to_I02": Segment("B_to_I02", "B", "I02", Direction.SOUTH),
    "I02_to_B": Segment("I02_to_B", "I02", "B", Direction.NORTH),
    "C_to_I22": Segment("C_to_I22", "C", "I22", Direction.WEST),
    "I22_to_C": Segment("I22_to_C", "I22", "C", Direction.EAST),
    "D_to_I20": Segment("D_to_I20", "D", "I20", Direction.NORTH),
    "I20_to_D": Segment("I20_to_D", "I20", "D", Direction.SOUTH),
}


def build_nodes() -> Dict[str, Node]:
    return dict(NODES)


def build_segments() -> Dict[str, Segment]:
    return dict(SEGMENTS)


def is_valid_crossing_transition(
    segments: Dict[str, Segment],
    incoming_segment_id: str,
    outgoing_segment_id: str,
) -> bool:
    incoming = segments.get(incoming_segment_id)
    outgoing = segments.get(outgoing_segment_id)
    if incoming is None or outgoing is None:
        return False
    return incoming.to_node == outgoing.from_node


def is_u_turn_transition(
    segments: Dict[str, Segment],
    incoming_segment_id: str,
    outgoing_segment_id: str,
) -> bool:
    if not is_valid_crossing_transition(segments, incoming_segment_id, outgoing_segment_id):
        return False
    incoming = segments[incoming_segment_id]
    outgoing = segments[outgoing_segment_id]
    if not incoming.to_node.startswith("I"):
        return False
    return outgoing.to_node == incoming.from_node


_RIGHT_TURN_OF: Dict[Direction, Direction] = {
    Direction.NORTH: Direction.EAST,
    Direction.EAST:  Direction.SOUTH,
    Direction.SOUTH: Direction.WEST,
    Direction.WEST:  Direction.NORTH,
}


def is_right_turn_transition(
    segments: Dict[str, Segment],
    incoming_segment_id: str,
    outgoing_segment_id: str,
) -> bool:
    if not is_valid_crossing_transition(segments, incoming_segment_id, outgoing_segment_id):
        return False
    incoming = segments[incoming_segment_id]
    outgoing = segments[outgoing_segment_id]
    return outgoing.direction == _RIGHT_TURN_OF[incoming.direction]
```

---

### 8.2 `i_group_phaseA.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from common_model import (
    CrossingGrant,
    CrossingRequest,
    Direction,
    IntersectionLightState,
    NodeType,
    VehicleState,
    build_nodes,
    build_segments,
    is_right_turn_transition,
    is_u_turn_transition,
    is_valid_crossing_transition,
)


@dataclass
class SafetyReport:
    collisions: int = 0
    red_light_violations: int = 0
    simultaneous_green_violations: int = 0
    invalid_grant_violations: int = 0
    wrong_direction_violations: int = 0
    u_turn_violations: int = 0
    right_turn_violations: int = 0


@dataclass
class IntersectionController:
    intersection_id: str
    light_state: IntersectionLightState
    starvation_counter: Dict[Direction, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for d in Direction:
            self.starvation_counter.setdefault(d, 0)

    def select_green_direction(
        self,
        waiting_by_direction: Dict[Direction, int],
    ) -> Optional[Direction]:
        best_dir = None
        best_score = -1
        for d in Direction:
            score = waiting_by_direction.get(d, 0) + self.starvation_counter.get(d, 0)
            if score > best_score and waiting_by_direction.get(d, 0) > 0:
                best_score = score
                best_dir = d
        return best_dir

    def update_light(
        self,
        waiting_by_direction: Dict[Direction, int],
    ) -> None:
        chosen = self.select_green_direction(waiting_by_direction)
        self.light_state.green_direction = chosen
        for d in Direction:
            if d == chosen:
                self.starvation_counter[d] = 0
            else:
                if waiting_by_direction.get(d, 0) > 0:
                    self.starvation_counter[d] += 1
                else:
                    self.starvation_counter[d] = 0


class InfrastructureSimulator:
    def __init__(self) -> None:
        self.nodes = build_nodes()
        self.segments = build_segments()
        self.intersection_ids = [
            node_id
            for node_id, node in self.nodes.items()
            if node.node_type == NodeType.INTERSECTION
        ]
        self.controllers: Dict[str, IntersectionController] = {
            iid: IntersectionController(
                intersection_id=iid,
                light_state=IntersectionLightState(intersection_id=iid, green_direction=None),
            )
            for iid in self.intersection_ids
        }
        self.time_step = 0
        self.safety_report = SafetyReport()

    def get_incoming_waiting_vehicles(
        self,
        vehicles: Dict[str, VehicleState],
    ) -> Dict[str, List[VehicleState]]:
        waiting: Dict[str, List[VehicleState]] = {iid: [] for iid in self.intersection_ids}
        for vehicle in vehicles.values():
            if vehicle.current_segment not in self.segments:
                continue
            seg = self.segments[vehicle.current_segment]
            if seg.to_node in self.intersection_ids:
                if vehicle.current_slot == seg.length_slots - 1 and vehicle.request_crossing:
                    waiting[seg.to_node].append(vehicle)
        return waiting

    def count_waiting_by_direction(
        self,
        intersection_id: str,
        waiting_vehicles: List[VehicleState],
    ) -> Dict[Direction, int]:
        counts = {d: 0 for d in Direction}
        for vehicle in waiting_vehicles:
            seg = self.segments[vehicle.current_segment]
            counts[seg.direction] += 1
        return counts

    def validate_request(
        self,
        vehicle: VehicleState,
    ) -> Tuple[bool, bool]:
        if vehicle.current_segment not in self.segments:
            self.safety_report.wrong_direction_violations += 1
            return False, False
        if vehicle.desired_next_segment is None or vehicle.desired_next_segment not in self.segments:
            self.safety_report.wrong_direction_violations += 1
            return False, False
        incoming_seg = self.segments[vehicle.current_segment]
        if vehicle.current_slot != incoming_seg.length_slots - 1:
            self.safety_report.wrong_direction_violations += 1
            return False, False
        if incoming_seg.to_node not in self.intersection_ids:
            self.safety_report.wrong_direction_violations += 1
            return False, False
        if not is_valid_crossing_transition(
            self.segments, vehicle.current_segment, vehicle.desired_next_segment,
        ):
            self.safety_report.wrong_direction_violations += 1
            return False, False
        if is_u_turn_transition(
            self.segments, vehicle.current_segment, vehicle.desired_next_segment,
        ):
            self.safety_report.u_turn_violations += 1
            return False, True
        if is_right_turn_transition(
            self.segments, vehicle.current_segment, vehicle.desired_next_segment,
        ):
            self.safety_report.right_turn_violations += 1
            return False, False
        return True, False

    def build_crossing_requests(
        self,
        vehicles: Dict[str, VehicleState],
    ) -> Dict[str, List[CrossingRequest]]:
        requests: Dict[str, List[CrossingRequest]] = {iid: [] for iid in self.intersection_ids}
        for vehicle in vehicles.values():
            if not vehicle.request_crossing:
                continue
            is_valid, _ = self.validate_request(vehicle)
            if not is_valid:
                continue
            incoming_seg = self.segments[vehicle.current_segment]
            intersection_id = incoming_seg.to_node
            if intersection_id not in self.intersection_ids:
                continue
            requests[intersection_id].append(
                CrossingRequest(
                    car_id=vehicle.car_id,
                    intersection_id=intersection_id,
                    incoming_segment=vehicle.current_segment,
                    outgoing_segment=vehicle.desired_next_segment,
                )
            )
        return requests

    def select_one_grant(
        self,
        intersection_id: str,
        requests: List[CrossingRequest],
        vehicles: Dict[str, VehicleState],
    ) -> Optional[CrossingGrant]:
        green_dir = self.controllers[intersection_id].light_state.green_direction
        if green_dir is None:
            return None
        eligible: List[CrossingRequest] = []
        for req in requests:
            incoming_seg = self.segments[req.incoming_segment]
            if incoming_seg.direction == green_dir:
                eligible.append(req)
        if not eligible:
            return None
        eligible.sort(key=lambda r: r.car_id)
        chosen = eligible[0]
        return CrossingGrant(
            intersection_id=intersection_id,
            car_id=chosen.car_id,
            granted=True,
        )

    def compute_congestion_map(
        self,
        vehicles: Dict[str, VehicleState],
    ) -> Dict[str, int]:
        congestion = {iid: 0 for iid in self.intersection_ids}
        for vehicle in vehicles.values():
            if vehicle.current_segment not in self.segments:
                continue
            seg = self.segments[vehicle.current_segment]
            if seg.to_node in self.intersection_ids and vehicle.stopped:
                congestion[seg.to_node] += 1
        return congestion

    def detect_collisions(
        self,
        vehicles: Dict[str, VehicleState],
    ) -> None:
        occupied: Dict[Tuple[str, int], str] = {}
        for vehicle in vehicles.values():
            if vehicle.current_segment not in self.segments:
                continue
            loc = (vehicle.current_segment, vehicle.current_slot)
            if loc in occupied:
                self.safety_report.collisions += 1
            else:
                occupied[loc] = vehicle.car_id

    def check_safety(
        self,
        vehicles: Dict[str, VehicleState],
        grants: List[CrossingGrant],
        requests_by_intersection: Dict[str, List[CrossingRequest]],
    ) -> None:
        for iid, controller in self.controllers.items():
            green = controller.light_state.green_direction
            green_count = 1 if green is not None else 0
            if green_count > 1:
                self.safety_report.simultaneous_green_violations += 1

        grant_map: Dict[Tuple[str, str], CrossingGrant] = {
            (g.intersection_id, g.car_id): g for g in grants if g.granted
        }

        for iid, reqs in requests_by_intersection.items():
            green_dir = self.controllers[iid].light_state.green_direction
            for req in reqs:
                key = (iid, req.car_id)
                if key in grant_map:
                    incoming_seg = self.segments[req.incoming_segment]
                    if green_dir is None or incoming_seg.direction != green_dir:
                        self.safety_report.invalid_grant_violations += 1
                        self.safety_report.red_light_violations += 1
                    if not is_valid_crossing_transition(
                        self.segments, req.incoming_segment, req.outgoing_segment,
                    ):
                        self.safety_report.invalid_grant_violations += 1
                        self.safety_report.wrong_direction_violations += 1
                    if is_u_turn_transition(
                        self.segments, req.incoming_segment, req.outgoing_segment,
                    ):
                        self.safety_report.invalid_grant_violations += 1
                        self.safety_report.u_turn_violations += 1
                    if is_right_turn_transition(
                        self.segments, req.incoming_segment, req.outgoing_segment,
                    ):
                        self.safety_report.invalid_grant_violations += 1
                        self.safety_report.right_turn_violations += 1

        self.detect_collisions(vehicles)

    def step(
        self,
        vehicles: Dict[str, VehicleState],
    ) -> Dict[str, object]:
        self.time_step += 1
        waiting = self.get_incoming_waiting_vehicles(vehicles)
        for iid in self.intersection_ids:
            waiting_by_dir = self.count_waiting_by_direction(iid, waiting[iid])
            self.controllers[iid].update_light(waiting_by_dir)
        requests_by_intersection = self.build_crossing_requests(vehicles)
        grants: List[CrossingGrant] = []
        for iid in self.intersection_ids:
            grant = self.select_one_grant(iid, requests_by_intersection[iid], vehicles)
            if grant is not None:
                grants.append(grant)
        congestion = self.compute_congestion_map(vehicles)
        self.check_safety(vehicles, grants, requests_by_intersection)
        lights_out = {
            iid: controller.light_state.green_direction.value
            if controller.light_state.green_direction is not None else None
            for iid, controller in self.controllers.items()
        }
        grants_out = [
            {"intersection_id": g.intersection_id, "car_id": g.car_id, "granted": g.granted}
            for g in grants
        ]
        return {
            "time_step": self.time_step,
            "lights": lights_out,
            "crossing_grants": grants_out,
            "congestion_map": congestion,
            "safety_report": {
                "collisions": self.safety_report.collisions,
                "red_light_violations": self.safety_report.red_light_violations,
                "simultaneous_green_violations": self.safety_report.simultaneous_green_violations,
                "invalid_grant_violations": self.safety_report.invalid_grant_violations,
                "wrong_direction_violations": self.safety_report.wrong_direction_violations,
                "u_turn_violations": self.safety_report.u_turn_violations,
                "right_turn_violations": self.safety_report.right_turn_violations,
            },
        }


if __name__ == "__main__":
    sim = InfrastructureSimulator()
    vehicles = {
        "car_1": VehicleState(
            car_id="car_1", current_segment="A_to_I00", current_slot=29,
            visited_B=False, visited_C=False, visited_D=False, current_target="B",
            stopped=True, request_crossing=True, desired_next_segment="I00_to_I01",
        ),
        "car_2": VehicleState(
            car_id="car_2", current_segment="I10_to_I11", current_slot=29,
            visited_B=False, visited_C=False, visited_D=False, current_target="C",
            stopped=True, request_crossing=True, desired_next_segment="I11_to_I12",
        ),
        "car_3": VehicleState(
            car_id="car_3", current_segment="I01_to_I11", current_slot=12,
            visited_B=True, visited_C=False, visited_D=False, current_target="D",
            stopped=False, request_crossing=False, desired_next_segment=None,
        ),
    }
    result = sim.step(vehicles)
    print(result)
```

---

### 8.3 `v_group_phaseA.py`

```python
from __future__ import annotations

from typing import Dict, List, Optional, Set

from common_model import (
    Segment,
    VehicleState,
    build_nodes,
    build_segments,
    is_right_turn_transition,
    is_u_turn_transition,
    is_valid_crossing_transition,
)


class RoutePlanner:
    def __init__(self, segments: Dict[str, Segment]) -> None:
        self.segments = segments
        self.outgoing_by_node: Dict[str, List[str]] = {}
        for seg_id, seg in segments.items():
            self.outgoing_by_node.setdefault(seg.from_node, []).append(seg_id)

    def get_next_target(self, vehicle: VehicleState) -> str:
        remaining = []
        if not vehicle.visited_B:
            remaining.append("B")
        if not vehicle.visited_C:
            remaining.append("C")
        if not vehicle.visited_D:
            remaining.append("D")
        if remaining:
            return remaining[0]
        return "A"

    def choose_next_segment(
        self,
        current_segment: str,
        current_node: str,
        target_node: str,
        congestion_map: Dict[str, int],
    ) -> Optional[str]:
        candidates = self.outgoing_by_node.get(current_node, [])
        if not candidates:
            return None
        best_seg = None
        best_score = float("inf")
        for seg_id in candidates:
            if not is_valid_crossing_transition(self.segments, current_segment, seg_id):
                continue
            if is_u_turn_transition(self.segments, current_segment, seg_id):
                continue
            if is_right_turn_transition(self.segments, current_segment, seg_id):
                continue
            seg = self.segments[seg_id]
            score = self.estimate_cost(seg.to_node, target_node, congestion_map)
            if score < best_score:
                best_score = score
                best_seg = seg_id
        return best_seg

    def estimate_cost(
        self,
        node: str,
        target: str,
        congestion_map: Dict[str, int],
    ) -> int:
        if node == target:
            return 0
        score = 10
        if node.startswith("I") and target.startswith("I"):
            score += abs(int(node[1]) - int(target[1])) * 2
            score += abs(int(node[2]) - int(target[2])) * 2
        elif node.startswith("I") and target in {"A", "B", "C", "D"}:
            terminal_anchor = {"A": "I00", "B": "I02", "C": "I22", "D": "I20"}[target]
            score += abs(int(node[1]) - int(terminal_anchor[1])) * 2
            score += abs(int(node[2]) - int(terminal_anchor[2])) * 2
        elif node in {"A", "B", "C", "D"}:
            score += 3
        score += congestion_map.get(node, 0)
        return score


class VehicleSimulator:
    def __init__(self) -> None:
        self.nodes = build_nodes()
        self.segments = build_segments()
        self.route_planner = RoutePlanner(self.segments)
        self.vehicles: Dict[str, VehicleState] = {}
        self.time_step = 0
        self.completed_tours = 0
        self.red_light_violations = 0
        self.collisions = 0
        self.illegal_direction_violations = 0
        self.u_turn_violations = 0
        self.right_turn_violations = 0

    def add_vehicle(self, car_id: str) -> None:
        self.vehicles[car_id] = VehicleState(
            car_id=car_id, current_segment="A_to_I00", current_slot=0,
            visited_B=False, visited_C=False, visited_D=False,
            current_target="B", stopped=False,
            request_crossing=False, desired_next_segment=None,
        )

    def mark_visit_if_needed(self, vehicle: VehicleState) -> None:
        seg = self.segments[vehicle.current_segment]
        node = seg.to_node if vehicle.current_slot == seg.length_slots - 1 else None
        if node == "B":
            vehicle.visited_B = True
        elif node == "C":
            vehicle.visited_C = True
        elif node == "D":
            vehicle.visited_D = True
        vehicle.current_target = self.route_planner.get_next_target(vehicle)

    VISIBILITY_SLOTS = 15

    def is_front_blocked(self, vehicle: VehicleState) -> bool:
        nearest_slot = None
        for other in self.vehicles.values():
            if other.car_id == vehicle.car_id:
                continue
            if other.current_segment == vehicle.current_segment and other.current_slot > vehicle.current_slot:
                if nearest_slot is None or other.current_slot < nearest_slot:
                    nearest_slot = other.current_slot
        if nearest_slot is None:
            return False
        return (nearest_slot - vehicle.current_slot) <= self.VISIBILITY_SLOTS

    def build_crossing_request(
        self,
        vehicle: VehicleState,
        congestion_map: Dict[str, int],
    ) -> None:
        seg = self.segments[vehicle.current_segment]
        current_node = seg.to_node
        next_seg = self.route_planner.choose_next_segment(
            current_segment=vehicle.current_segment,
            current_node=current_node,
            target_node=vehicle.current_target,
            congestion_map=congestion_map,
        )
        vehicle.request_crossing = True
        vehicle.desired_next_segment = next_seg

    def advance_from_terminal(
        self,
        vehicle: VehicleState,
        congestion_map: Dict[str, int],
    ) -> None:
        seg = self.segments[vehicle.current_segment]
        next_seg = self.route_planner.choose_next_segment(
            current_segment=vehicle.current_segment,
            current_node=seg.to_node,
            target_node=vehicle.current_target,
            congestion_map=congestion_map,
        )
        if next_seg is None:
            self.stay(vehicle)
            vehicle.request_crossing = False
            vehicle.desired_next_segment = None
            return
        if not is_valid_crossing_transition(self.segments, vehicle.current_segment, next_seg):
            self.illegal_direction_violations += 1
            self.stay(vehicle)
            vehicle.request_crossing = False
            vehicle.desired_next_segment = None
            return
        vehicle.current_segment = next_seg
        vehicle.current_slot = 0
        vehicle.stopped = False
        vehicle.request_crossing = False
        vehicle.desired_next_segment = None

    def move_inside_segment(self, vehicle: VehicleState) -> None:
        if vehicle.current_slot < self.segments[vehicle.current_segment].length_slots - 1:
            vehicle.current_slot += 1
            vehicle.stopped = False
            vehicle.request_crossing = False
            vehicle.desired_next_segment = None

    def stay(self, vehicle: VehicleState) -> None:
        vehicle.stopped = True

    def apply_intersection_result(
        self,
        vehicle: VehicleState,
        lights: Dict[str, Optional[str]],
        crossing_grants: List[Dict[str, object]],
    ) -> None:
        seg = self.segments[vehicle.current_segment]
        intersection_id = seg.to_node
        granted = False
        for g in crossing_grants:
            if g["car_id"] == vehicle.car_id and g["intersection_id"] == intersection_id and g["granted"]:
                granted = True
                break
        green_dir = lights.get(intersection_id)
        if granted and vehicle.desired_next_segment is not None:
            if not is_valid_crossing_transition(
                self.segments, vehicle.current_segment, vehicle.desired_next_segment,
            ):
                self.illegal_direction_violations += 1
                vehicle.stopped = True
                return
            if is_u_turn_transition(
                self.segments, vehicle.current_segment, vehicle.desired_next_segment,
            ):
                self.u_turn_violations += 1
                vehicle.stopped = True
                return
            if is_right_turn_transition(
                self.segments, vehicle.current_segment, vehicle.desired_next_segment,
            ):
                self.right_turn_violations += 1
                vehicle.stopped = True
                return
            current_direction = seg.direction.value
            if green_dir is None or green_dir != current_direction:
                self.red_light_violations += 1
            vehicle.current_segment = vehicle.desired_next_segment
            vehicle.current_slot = 0
            vehicle.stopped = False
            vehicle.request_crossing = False
            vehicle.desired_next_segment = None
            return
        vehicle.stopped = True

    def check_collision(self) -> None:
        occupied: Set[tuple[str, int]] = set()
        for vehicle in self.vehicles.values():
            loc = (vehicle.current_segment, vehicle.current_slot)
            if loc in occupied:
                self.collisions += 1
            occupied.add(loc)

    def build_vehicle_snapshot(self) -> Dict[str, Dict[str, object]]:
        return {
            car_id: {
                "current_segment": v.current_segment,
                "current_slot": v.current_slot,
                "visited_B": v.visited_B,
                "visited_C": v.visited_C,
                "visited_D": v.visited_D,
                "current_target": v.current_target,
                "stopped": v.stopped,
                "request_crossing": v.request_crossing,
                "desired_next_segment": v.desired_next_segment,
            }
            for car_id, v in self.vehicles.items()
        }

    def prepare_requests(
        self,
        congestion_map: Dict[str, int],
    ) -> Dict[str, Dict[str, object]]:
        for vehicle in self.vehicles.values():
            vehicle.current_target = self.route_planner.get_next_target(vehicle)
            if self.is_front_blocked(vehicle):
                self.stay(vehicle)
                vehicle.request_crossing = False
                vehicle.desired_next_segment = None
                continue
            seg = self.segments[vehicle.current_segment]
            if vehicle.current_slot < seg.length_slots - 1:
                self.move_inside_segment(vehicle)
            elif seg.to_node in {"A", "B", "C", "D"}:
                self.mark_visit_if_needed(vehicle)
                self.advance_from_terminal(vehicle, congestion_map)
            else:
                self.build_crossing_request(vehicle, congestion_map)
        self.check_collision()
        return self.build_vehicle_snapshot()

    def apply_i_group_output(
        self,
        lights: Dict[str, Optional[str]],
        crossing_grants: List[Dict[str, object]],
    ) -> None:
        for vehicle in self.vehicles.values():
            seg = self.segments[vehicle.current_segment]
            if vehicle.request_crossing and seg.to_node.startswith("I"):
                self.apply_intersection_result(vehicle, lights, crossing_grants)
            self.mark_visit_if_needed(vehicle)
            if vehicle.visited_B and vehicle.visited_C and vehicle.visited_D:
                end_seg = self.segments[vehicle.current_segment]
                if end_seg.to_node == "A" and vehicle.current_slot == end_seg.length_slots - 1:
                    self.completed_tours += 1
                    vehicle.current_segment = "A_to_I00"
                    vehicle.current_slot = 0
                    vehicle.visited_B = False
                    vehicle.visited_C = False
                    vehicle.visited_D = False
                    vehicle.current_target = "B"
                    vehicle.stopped = False
                    vehicle.request_crossing = False
                    vehicle.desired_next_segment = None
        self.check_collision()

    def step(
        self,
        i_group_output: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        self.time_step += 1
        if i_group_output is None:
            i_group_output = {"lights": {}, "crossing_grants": [], "congestion_map": {}}
        congestion_map = i_group_output.get("congestion_map", {})
        lights = i_group_output.get("lights", {})
        crossing_grants = i_group_output.get("crossing_grants", [])
        vehicles_for_i_group = self.prepare_requests(congestion_map)
        self.apply_i_group_output(lights, crossing_grants)
        current_vehicle_states = self.build_vehicle_snapshot()
        return {
            "time_step": self.time_step,
            "vehicles": current_vehicle_states,
            "vehicles_for_i_group": vehicles_for_i_group,
            "stats": {
                "completed_tours": self.completed_tours,
                "red_light_violations": self.red_light_violations,
                "collisions": self.collisions,
                "illegal_direction_violations": self.illegal_direction_violations,
                "u_turn_violations": self.u_turn_violations,
                "right_turn_violations": self.right_turn_violations,
            },
        }


if __name__ == "__main__":
    v_sim = VehicleSimulator()
    v_sim.add_vehicle("car_1")
    v_sim.add_vehicle("car_2")

    out1 = v_sim.step()
    print("Step 1")
    print(out1)

    i_group_output = {
        "lights": {"I00": "east", "I11": "north"},
        "crossing_grants": [
            {"intersection_id": "I00", "car_id": "car_1", "granted": True}
        ],
        "congestion_map": {"I00": 1, "I11": 2},
    }
    out2 = v_sim.step(i_group_output)
    print("Step 2")
    print(out2)
```
