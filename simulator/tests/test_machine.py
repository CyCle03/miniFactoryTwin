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
