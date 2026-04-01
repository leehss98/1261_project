# ECEN723 Introduction to Formal Verification Spring 2026

## Project Overview

This project is to design a simplified traffic system and verify its properties.

The road system has three horizontal roads and three vertical roads. Each circle is a road intersection. Each vehicle departs from A, visits B, C, and D in any order, and returns to A. The distance between two neighboring circles is 0.5 mile, and the distance from a square to its adjacent circle is 1/30 mile. A car can either run with a speed of 30 miles per hour or stop.

Each road segment between two intersections is divided into 30 uniform-sized slots. Each control step, or time step, is 2 seconds. At each control step, a car must be within a slot. In the next step, it can either stay there or move to the next slot.

Along each direction, there is a single lane. For example, in the figure below, there is one intersection among four edges. Car `a` is at the rightmost slot of the left segment. In the next step, it can do one of the following:

1. Go straight to the leftmost slot of the right segment.
2. Turn right to the topmost slot of the bottom segment.
3. Turn left to the bottom slot of the top segment.

Between two consecutive time steps, there is at most one car crossing an intersection. If at any moment there are more than one car in the same slot, that is counted as a collision. A car must stop at a red light and cannot make a right turn.

The problem formulation is to maximize the total number of cars reaching each of the four square node destinations per hour, without any collision and without any red-light signal violation. Each i-group must verify and report the number of collisions and red-light signal violations. There are green and red lights, but no yellow lights.

## Additional Specifications

- On each direction of each road, there is a single lane.
- At each intersection, between two consecutive time steps, there is at most one car crossing the intersection.
- There are at most four signal lights at each intersection. At any time, at most one light can be green.
- A car can see another car in front of it on the same direction with distance no more than 0.5 mile away without any other third car in between.
- At an intersection, a car can see other cars at the same intersection.
- A fundamental constraint is that a car cannot run in a lane opposite its driving direction.
- U-turn is not allowed.
- A v-group knows the number of cars stopping at each intersection as congestion information. "Stopping" means no move from the previous time step to the current time step.
- The three constraints, no collision, no violation of red light signal, and no run in the opposite direction lane, should be verified in both i-group and v-group. The verification results should match.
- If there is collision, the reason may be from either i-group or v-group, depending on the actual case.
- At a time step, if car P sees another car Q in front of P along the same direction, car P cannot move to the next time step.

## Team Structure

There are 77 students in the class including the online section. They are divided into 19 teams. Each team has one infrastructure group (i-group) and one vehicle group (v-group). Each group has two students.

You are required to sign up in a Google spreadsheet to form groups by March 23, Monday. If you do not sign up, the instructor will assign groups arbitrarily.

## Roles of Each Group

### i-group

An i-group will develop software simulating road infrastructure. It can receive vehicle signals from the v-group to know vehicle location, speed, and moving directions. However, the i-group does not know whether a car will turn or go straight at an intersection. It will decide the green or red light status at each road intersection.

### v-group

Each v-group will develop software simulating a number of vehicles in the road system. A vehicle starts from point A, visits B, C, and D in any order, and then returns to A. It can receive traffic congestion information from itself and then decide the best route to reach its destination in the shortest time.

## Evaluation Metrics

The results for both i-group and v-group are evaluated by:

- Overall throughput, defined as the number of cars completing the tour per hour
- The number of collisions
- The number of illegal running directions
- The number of U-turns
- The number of red-light violations

## Important Deadlines

1. Sign up groups by March 23, Monday.
2. Project Phase A design report (10 points) due on April 3, Friday.
3. Project Phase B (8 points) due on April 14, Tuesday.
4. Project Phase C verification report (12 points) due on April 28, Tuesday.

## Project Phases

### Phase A

Each group finishes its part of software design, debugging, and shows results.

### Phase B

The codes of the two groups in the same team are merged and debugged with results. The team must also find a verification tool and run a small example to demonstrate the use of this tool.

### Phase C

Finish verifying specified properties for both i-group and v-group.
