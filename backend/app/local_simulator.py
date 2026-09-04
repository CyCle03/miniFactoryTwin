"""In-process adapter for running the Python simulator without MQTT.

This is intentionally a development-only transport. The machine behavior still
comes from ``simulator.machine``; only the MQTT hop is bypassed.
"""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress

from simulator.machine import MachineSimulator

from .models import CommandMessage, MachineState

StateHandler = Callable[[MachineState], Awaitable[None]]


class LocalSimulatorRuntime:
    def __init__(self, state_handler: StateHandler) -> None:
        self._machine = MachineSimulator()
        self._state_handler = state_handler
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run(), name="local-simulator")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def handle_command(self, command: CommandMessage) -> None:
        self._machine.handle_command(command.command.value)

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        previous_tick = loop.time()
        next_publish = previous_tick

        while self._running:
            current_tick = loop.time()
            self._machine.tick(min(current_tick - previous_tick, 0.25), current_tick)
            previous_tick = current_tick

            if current_tick >= next_publish:
                state = MachineState.model_validate(self._machine.state(current_tick))
                await self._state_handler(state)
                next_publish = current_tick + 0.1

            await asyncio.sleep(0.05)

