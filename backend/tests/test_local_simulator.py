import asyncio

from backend.app.local_simulator import LocalSimulatorRuntime
from backend.app.models import CommandMessage, CommandName, MachineState


def test_local_runtime_streams_state_and_applies_commands() -> None:
    received: list[MachineState] = []

    async def capture(state: MachineState) -> None:
        received.append(state)

    async def scenario() -> None:
        runtime = LocalSimulatorRuntime(capture)
        await runtime.start()
        await runtime.handle_command(CommandMessage(command=CommandName.START))
        await asyncio.sleep(0.16)
        await runtime.stop()

    asyncio.run(scenario())

    assert received
    assert received[-1].machine.running is True
    assert received[-1].conveyor.running is True

