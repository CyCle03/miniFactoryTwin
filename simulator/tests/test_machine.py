from simulator.constants import SimulationConfig
from simulator.machine import MachineSimulator
from simulator.product import Product, ProductResult


def test_start_spawns_and_moves_a_product() -> None:
    machine = MachineSimulator(seed=1, initial_time=100.0)
    machine.handle_command("start")
    machine.tick(0.5, now=100.0)

    state = machine.state(now=100.0)
    assert state["machine"]["running"] is True  # type: ignore[index]
    assert len(state["products"]) == 1  # type: ignore[arg-type]
    assert state["products"][0]["position"] == 7.0  # type: ignore[index]


def test_reject_product_activates_cylinder_and_counter() -> None:
    config = SimulationConfig(good_probability=0.0)
    machine = MachineSimulator(config=config, seed=1, initial_time=200.0)
    machine.handle_command("start")
    machine.products = [Product(1, 79.0, ProductResult.REJECT)]
    machine.tick(0.1, now=199.0)

    state = machine.state(now=199.1)
    assert state["products"] == []
    assert state["cylinder"]["state"] == "extended"  # type: ignore[index]
    assert state["production"] == {"total": 1, "good": 0, "reject": 1, "ppm": 1}


def test_emergency_stop_freezes_motion_until_reset_and_restart() -> None:
    machine = MachineSimulator(seed=1, initial_time=300.0)
    machine.handle_command("start")
    machine.products = [Product(1, 30.0, ProductResult.GOOD)]
    machine.handle_command("emergency_stop")
    machine.tick(2.0, now=300.0)

    assert machine.products[0].position == 30.0
    assert machine.state(now=300.0)["machine"] == {
        "power": True,
        "running": False,
        "emergency": True,
    }

    machine.handle_command("emergency_reset")
    machine.handle_command("start")
    machine.tick(1.0, now=301.0)
    assert machine.products[0].position == 44.0


def test_reset_clears_products_and_counts() -> None:
    machine = MachineSimulator(seed=1)
    machine.total_count = 4
    machine.good_count = 3
    machine.reject_count = 1
    machine.products = [Product(1, 10.0, ProductResult.GOOD)]
    machine.handle_command("reset")

    state = machine.state(now=400.0)
    assert state["production"] == {"total": 0, "good": 0, "reject": 0, "ppm": 0}
    assert state["products"] == []
    assert state["machine"]["running"] is False  # type: ignore[index]


def test_good_product_event_flow_and_cycle_time() -> None:
    config = SimulationConfig(good_probability=1.0)
    machine = MachineSimulator(config=config, seed=1, initial_time=100.0)
    machine.handle_command("start")
    machine.tick(0, now=100.0)
    machine.tick(8, now=108.0)
    events = machine.drain_events()
    types = [event["event_type"] for event in events]
    assert "product_entered" in types
    assert "inspection_completed" in types
    assert "product_completed" in types
    completed = next(event for event in events if event["event_type"] == "product_completed")
    assert completed["metadata"]["cycle_time_seconds"] == 8.0


def test_repeated_emergency_commands_do_not_duplicate_events() -> None:
    machine = MachineSimulator(seed=1)
    machine.handle_command("emergency_stop")
    machine.handle_command("emergency_stop")
    machine.handle_command("emergency_reset")
    machine.handle_command("emergency_reset")
    types = [event["event_type"] for event in machine.drain_events()]
    assert types.count("emergency_stop_activated") == 1
    assert types.count("emergency_stop_reset") == 1


def test_reject_product_emits_reject_and_completion_events() -> None:
    config = SimulationConfig(good_probability=0.0)
    machine = MachineSimulator(config=config, seed=1, initial_time=500.0)
    machine.handle_command("start")
    machine.tick(0, now=500.0)
    machine.tick(6, now=506.0)
    events = machine.drain_events()
    types = [event["event_type"] for event in events]
    assert "product_rejected" in types
    assert "product_completed" in types
    completed = next(event for event in events if event["event_type"] == "product_completed")
    assert completed["metadata"]["result"] == "REJECT"
    assert completed["metadata"]["cycle_time_seconds"] == 6.0
