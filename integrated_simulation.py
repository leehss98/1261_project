"""
Integrated simulation: merges v-group and i-group into a single
synchronised loop so that both sides share full state each time step.

Phase B, Task B.1
"""
import argparse
import sys
from typing import Dict, List, Optional

from common_model import VehicleState
from i_group_phaseA import InfrastructureSimulator
from v_group_phaseA import VehicleSimulator


class IntegratedSimulation:
    """Wraps VehicleSimulator and InfrastructureSimulator with a 3-phase
    step protocol that gives both modules same-step mutual visibility."""

    def __init__(self, num_vehicles: int = 5) -> None:
        self.v_sim = VehicleSimulator()
        self.i_sim = InfrastructureSimulator()

        for i in range(1, num_vehicles + 1):
            self.v_sim.add_vehicle(f"car_{i}")

        self.time_step: int = 0
        self.congestion_map: Dict[str, int] = {}

    def step(self) -> dict:
        """Execute one unified simulation tick."""
        self.time_step += 1
        self.v_sim.time_step = self.time_step

        # Phase 1: vehicles advance within segments and build crossing requests
        vehicles_snapshot = self.v_sim.prepare_requests(self.congestion_map)

        # Phase 2: i-group sees current vehicle positions, decides lights/grants
        i_out = self.i_sim.step(vehicles_snapshot)

        # Phase 3: vehicles apply the CURRENT lights and grants (no one-step lag)
        self.v_sim.apply_i_group_output(
            i_out["lights"], i_out["crossing_grants"]
        )

        self.congestion_map = i_out.get("congestion_map", {})

        return {
            "time_step": self.time_step,
            "vehicles": self.v_sim.build_vehicle_snapshot(),
            "lights": i_out["lights"],
            "crossing_grants": i_out["crossing_grants"],
            "congestion_map": self.congestion_map,
            "safety_report": self._merge_safety_reports(i_out["safety_report"]),
            "throughput": {
                "completed_tours": self.v_sim.completed_tours,
            },
        }

    def _merge_safety_reports(self, i_safety: dict) -> dict:
        """Combine violation counts from both simulators for cross-validation.
        Turn-type violations (U-turn, right-turn) are only tracked by v-group
        because the i-group does not know the vehicle's intended direction."""
        return {
            "collisions_i": i_safety["collisions"],
            "collisions_v": self.v_sim.collisions,
            "red_light_violations_i": i_safety["red_light_violations"],
            "red_light_violations_v": self.v_sim.red_light_violations,
            "simultaneous_green_violations": i_safety["simultaneous_green_violations"],
            "invalid_grant_violations": i_safety["invalid_grant_violations"],
            "wrong_direction_violations_i": i_safety["wrong_direction_violations"],
            "illegal_direction_violations_v": self.v_sim.illegal_direction_violations,
            "u_turn_violations_v": self.v_sim.u_turn_violations,
            "right_turn_violations_v": self.v_sim.right_turn_violations,
        }

    def run(
        self, num_steps: int = 200, print_interval: int = 10
    ) -> dict:
        """Run the full simulation loop."""
        result: dict = {}
        for _ in range(num_steps):
            result = self.step()
            if self.time_step == 1 or self.time_step % print_interval == 0:
                self._print_step_summary(result)

        self._print_final_summary(result)
        return result

    def run_graphical(self, num_steps: int = 200) -> None:
        """Run simulation with tkinter GUI animation."""
        import tkinter as tk
        from traffic_gui import TrafficVisualization, GraphicalSimulationRunner

        root = tk.Tk()
        root.title("ECEN 723 Traffic Simulation")
        root.resizable(False, False)
        vis = TrafficVisualization(root)
        runner = GraphicalSimulationRunner(self, vis, num_steps, root)
        runner.start()
        root.mainloop()

    def _print_step_summary(self, result: dict) -> None:
        step = result["time_step"]
        print(f"\n--- Step {step} ---")
        for cid, v in result["vehicles"].items():
            print(
                f"  {cid}: seg={v['current_segment']}  slot={v['current_slot']}  "
                f"target={v['current_target']}  stopped={v['stopped']}  "
                f"req={v['request_crossing']}"
            )
        active_lights = {k: v for k, v in result["lights"].items() if v}
        if active_lights:
            print(f"  lights: {active_lights}")
        if result["crossing_grants"]:
            print(f"  grants: {result['crossing_grants']}")
        print(f"  tours completed: {result['throughput']['completed_tours']}")

    def _print_final_summary(self, result: dict) -> None:
        print("\n" + "=" * 60)
        print("  FINAL SUMMARY")
        print("=" * 60)
        print(f"  Total steps: {result['time_step']}")
        print(f"  Tours completed: {result['throughput']['completed_tours']}")
        print()
        print("  Safety violations (i-group / v-group):")
        sr = result["safety_report"]
        print(f"    Collisions:             {sr['collisions_i']} / {sr['collisions_v']}")
        print(f"    Red-light violations:   {sr['red_light_violations_i']} / {sr['red_light_violations_v']}")
        print(f"    U-turn violations:      - / {sr['u_turn_violations_v']}")
        print(f"    Right-turn violations:  - / {sr['right_turn_violations_v']}")
        print(f"    Wrong/illegal dir:      {sr['wrong_direction_violations_i']} / {sr['illegal_direction_violations_v']}")
        print(f"    Simultaneous green:     {sr['simultaneous_green_violations']}")
        print(f"    Invalid grants:         {sr['invalid_grant_violations']}")
        print()
        for cid, v in result["vehicles"].items():
            print(
                f"  {cid}: seg={v['current_segment']}  slot={v['current_slot']}  "
                f"visited_B={v['visited_B']}  visited_C={v['visited_C']}  visited_D={v['visited_D']}"
            )
        print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Integrated traffic simulation (Phase B)")
    parser.add_argument("--vehicles", type=int, default=5, help="Number of vehicles (default: 5)")
    parser.add_argument("--steps", type=int, default=1000, help="Number of simulation steps (default: 1000)")
    parser.add_argument("--print-interval", type=int, default=10, help="Print every N steps (default: 10)")
    parser.add_argument("-G", "--graphical", action="store_true", help="Enable graphical animation mode")
    args = parser.parse_args()

    sim = IntegratedSimulation(num_vehicles=args.vehicles)
    if args.graphical:
        sim.run_graphical(num_steps=args.steps)
    else:
        sim.run(num_steps=args.steps, print_interval=args.print_interval)
