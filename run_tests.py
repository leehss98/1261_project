"""
Run all five test scenarios from the Phase A report and print actual output.
"""
import sys
import pprint

from common_model import VehicleState
from i_group_phaseA import InfrastructureSimulator
from v_group_phaseA import VehicleSimulator


def separator(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


# ── Test 7.1: i-group Standalone ─────────────────────────────────
separator("7.1  i-group Standalone Test")

sim = InfrastructureSimulator()
vehicles_71 = {
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
result = sim.step(vehicles_71)
pprint.pprint(result)


# ── Test 7.2: Starvation-Freedom ────────────────────────────────
separator("7.2  i-group Starvation-Freedom Test")

sim2 = InfrastructureSimulator()
for step in range(1, 5):
    vehicles_72 = {
        "car_east": VehicleState(
            car_id="car_east", current_segment="I10_to_I11", current_slot=29,
            visited_B=False, visited_C=False, visited_D=False, current_target="B",
            stopped=True, request_crossing=True, desired_next_segment="I11_to_I12",
        ),
        "car_north": VehicleState(
            car_id="car_north", current_segment="I21_to_I11", current_slot=29,
            visited_B=False, visited_C=False, visited_D=False, current_target="D",
            stopped=True, request_crossing=True, desired_next_segment="I11_to_I01",
        ),
    }
    r = sim2.step(vehicles_72)
    ctrl = sim2.controllers["I11"]
    from common_model import Direction
    stv_east = ctrl.starvation_counter[Direction.EAST]
    stv_north = ctrl.starvation_counter[Direction.NORTH]
    light = r["lights"]["I11"]
    grants = r["crossing_grants"]
    print(f"Step {step}: light={light}  grants={grants}")
    print(f"         starvation_east={stv_east}  starvation_north={stv_north}")


# ── Test 7.3: Illegal Transition Rejection ───────────────────────
separator("7.3  i-group Illegal Transition Rejection Test")

sim3 = InfrastructureSimulator()
vehicles_73 = {
    "car_ok": VehicleState(
        car_id="car_ok", current_segment="A_to_I00", current_slot=29,
        visited_B=False, visited_C=False, visited_D=False, current_target="B",
        stopped=True, request_crossing=True, desired_next_segment="I00_to_I01",
    ),
    "car_uturn": VehicleState(
        car_id="car_uturn", current_segment="I00_to_I01", current_slot=29,
        visited_B=False, visited_C=False, visited_D=False, current_target="C",
        stopped=True, request_crossing=True, desired_next_segment="I01_to_I00",
    ),
    "car_right": VehicleState(
        car_id="car_right", current_segment="I21_to_I11", current_slot=29,
        visited_B=False, visited_C=False, visited_D=False, current_target="D",
        stopped=True, request_crossing=True, desired_next_segment="I11_to_I12",
    ),
}
r3 = sim3.step(vehicles_73)
print(f"lights:  { {k: v for k, v in r3['lights'].items() if v is not None} }")
print(f"grants:  {r3['crossing_grants']}")
print(f"safety:  {r3['safety_report']}")


# ── Test 7.4: v-group Standalone ────────────────────────────────
separator("7.4  v-group Standalone Test")

v_sim = VehicleSimulator()
v_sim.add_vehicle("car_1")
v_sim.add_vehicle("car_2")

out1 = v_sim.step()
print("Step 1:")
for cid, st in out1["vehicles"].items():
    print(f"  {cid}: seg={st['current_segment']}  slot={st['current_slot']}  "
          f"stopped={st['stopped']}  req={st['request_crossing']}")
print(f"  stats: {out1['stats']}")

i_group_output_74 = {
    "lights": {"I00": "east", "I11": "north"},
    "crossing_grants": [{"intersection_id": "I00", "car_id": "car_1", "granted": True}],
    "congestion_map": {"I00": 1, "I11": 2},
}
out2 = v_sim.step(i_group_output_74)
print("Step 2 (i-group signal: I00=east, car_1 granted):")
for cid, st in out2["vehicles"].items():
    print(f"  {cid}: seg={st['current_segment']}  slot={st['current_slot']}  "
          f"stopped={st['stopped']}  req={st['request_crossing']}")
print(f"  stats: {out2['stats']}")


# ── Test 7.5: End-to-End Integration (50 steps) ─────────────────
separator("7.5  End-to-End Integration Test (50 steps)")

i_sim5 = InfrastructureSimulator()
v_sim5 = VehicleSimulator()
v_sim5.add_vehicle("car_1")
v_sim5.add_vehicle("car_2")

highlight_steps = {1, 29, 30, 31, 48}
i_group_out = None

for step in range(1, 51):
    v_out = v_sim5.step(i_group_out)
    i_group_out = i_sim5.step(v_out["vehicles_for_i_group"])

    if step in highlight_steps:
        print(f"\nStep {step}:")
        for cid, st in v_out["vehicles"].items():
            print(f"  {cid}: seg={st['current_segment']}  slot={st['current_slot']}  "
                  f"stopped={st['stopped']}  req={st['request_crossing']}")
        lights_active = {k: v for k, v in i_group_out["lights"].items() if v}
        print(f"  lights: {lights_active}    grants: {i_group_out['crossing_grants']}")

# Final violation totals
print("\nFinal violation totals (i-group):", i_group_out["safety_report"])
print("Final violation totals (v-group):", v_out["stats"])
