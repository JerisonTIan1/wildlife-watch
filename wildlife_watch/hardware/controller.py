"""Deterministic command-level simulator; no vehicle dynamics or GPIO."""

from time import monotonic
from typing import Callable

from .protocol import validate_percent


class MockCarController:
    """Starts disarmed. Explicit disarm/arm is required after a latched stop.

    Watchdog evaluation is lazy: calls, properties, or tick() advance it. This
    avoids background threads and permits deterministic integration tests.
    """

    def __init__(self, *, clock: Callable[[], float] = monotonic):
        self._clock = clock
        self._state = "DISARMED"
        self._reason = "BOOT"
        self._speed = 0
        self._last_command = clock()

    def tick(self) -> None:
        if self._state in ("ARMED", "DRIVE"):
            if self._clock() - self._last_command >= 0.5:
                self._set("FAULT_LATCHED", "TIMEOUT")

    def _set(self, state: str, reason: str, speed: int = 0) -> None:
        self._state, self._reason, self._speed = state, reason, speed

    @property
    def state(self) -> str:
        self.tick()
        return self._state

    @property
    def reason(self) -> str:
        self.tick()
        return self._reason

    @property
    def speed_percent(self) -> int:
        self.tick()
        return self._speed

    @property
    def requested_duty(self) -> int:
        return (self.speed_percent * 255 + 50) // 100

    def arm(self) -> None:
        self.tick()
        if self._state != "DISARMED":
            self._set("FAULT_LATCHED", "DISARM_FIRST")
            raise RuntimeError("Explicit disarm required before arming")
        self._last_command = self._clock()
        self._set("ARMED", "OPERATOR")

    def disarm(self) -> None:
        self.tick()
        self._set("DISARMED", "OPERATOR")

    def set_speed(self, percent: int) -> None:
        self.tick()
        percent = validate_percent(percent)
        if percent == 0:
            self.stop()
            return
        if self._state not in ("ARMED", "DRIVE"):
            self._reason = "NOT_ARMED"
            raise RuntimeError("Motion denied: controller is not armed")
        self._last_command = self._clock()
        self._set("DRIVE", "COMMAND", percent)

    def stop(self) -> None:
        self.tick()
        self._set("BRAKE_LATCHED", "COMMAND")

    def fault(self) -> None:
        self.tick()
        self._set("FAULT_LATCHED", "HOST_FAULT")
