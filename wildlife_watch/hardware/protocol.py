"""Encode the existing V1 serial contract, including forward duty percentage."""


def validate_percent(percent: int) -> int:
    # Reject booleans, floats, NaN, and strings instead of silently coercing them.
    if type(percent) is not int:
        raise TypeError("percent must be an integer")
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return percent


class CommandEncoder:
    """Produces bytes only, not acknowledgements or evidence of physical motion.

    One owner per MCU connection. Never reset sequence on reconnect unless the
    MCU boot session is known to have changed. No automatic arming or retries.
    """

    def __init__(self, last_sequence: int = 0):
        if type(last_sequence) is not int or not 0 <= last_sequence <= 0xFFFFFFFF:
            raise ValueError("last_sequence must be an unsigned 32-bit integer")
        self._sequence = last_sequence

    @property
    def last_sequence(self) -> int:
        return self._sequence

    def _encode(self, command: str) -> bytes:
        if self._sequence == 0xFFFFFFFF:
            raise OverflowError("Sequence exhausted; do not wrap or auto-reset MCU")
        self._sequence += 1
        return f"V1,{self._sequence},{command}\n".encode("ascii")

    def arm(self) -> bytes:
        return self._encode("ARM")

    def disarm(self) -> bytes:
        return self._encode("DISARM")

    def set_speed(self, percent: int) -> bytes:
        percent = validate_percent(percent)
        return self.stop() if percent == 0 else self._encode(f"SPEED,{percent}")

    def stop(self) -> bytes:
        return self._encode("BRAKE")

    def fault(self) -> bytes:
        return self._encode("FAULT")
