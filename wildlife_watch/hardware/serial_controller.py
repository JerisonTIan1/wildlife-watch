"""Bounded V1 USB transport. Supports the documented SIM endpoint only."""

from dataclasses import dataclass
from time import perf_counter, sleep

from .protocol import CommandEncoder, validate_percent


@dataclass(frozen=True)
class Status:
    sequence: int
    state: str
    reason: str
    duty: int
    mode: str

    @classmethod
    def parse(cls, line):
        fields = line.decode("ascii").strip().split(",")
        if len(fields) != 6 or fields[0] != "V1" or fields[5] != "SIM":
            raise ValueError("Unsupported status/version/mode; only documented SIM firmware is supported")
        if not fields[1].isascii() or not fields[1].isdigit() or not fields[4].isdigit():
            raise ValueError("Invalid status numbers")
        sequence, duty = int(fields[1]), int(fields[4])
        if not 0 <= sequence <= 0xFFFFFFFF or not 0 <= duty <= 255:
            raise ValueError("Status out of range")
        if fields[2] not in ("DISARMED", "ARMED", "DRIVE", "CRUISE", "SLOW", "BRAKE_LATCHED", "FAULT_LATCHED"):
            raise ValueError("Unknown state")
        return cls(sequence, fields[2], fields[3], duty, fields[5])


class SerialCarController:
    """One command in flight; no motion retries, auto reconnect or replay.

    Matching status is observed MCU intent, not a guaranteed ACK or motor feedback.
    All calls must be serialized by the caller (demo uses its control lock).
    """
    backend_label = "USB SERIAL / SIM firmware (no GPIO)"

    def __init__(self, port, *, serial_factory=None, clock=perf_counter, wait=sleep, boot_timeout=4.):
        if serial_factory is None:
            import serial
            serial_factory = serial.Serial
        self.clock, self.wait = clock, wait
        self.encoder = CommandEncoder()
        self._state, self.speed_percent = "DISARMED", 0
        self.failed = False
        self.reason = "CONNECTING"
        self.buffer = bytearray()
        self.link = serial_factory(port=port, baudrate=115200, timeout=0, write_timeout=.05)
        try:
            # Fresh boot is mandatory: never guess the sequence of an existing session.
            deadline = clock() + boot_timeout
            while clock() < deadline:
                status = self._read()
                if status is not None:
                    if status != Status(0, "DISARMED", "BOOT", 0, "SIM"):
                        raise RuntimeError("Fresh BOOT required; disconnect motor power and deliberately reset Nano")
                    break
                wait(.002)
            else:
                raise RuntimeError("No fresh BOOT status; reset Nano and reopen explicitly")
            self._command(self.encoder.disarm(), "DISARMED", 0)
        except Exception:
            self.link.close()
            raise

    @property
    def state(self):
        return self._state

    def _read(self):
        for _ in range(8):
            if b"\n" in self.buffer:
                break
            chunk = self.link.read(128)
            if not chunk:
                break
            self.buffer.extend(chunk)
        if len(self.buffer) > 512:
            raise RuntimeError("Oversized status stream")
        if b"\n" not in self.buffer:
            return None
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        return Status.parse(line)

    def _trip(self, reason):
        self.failed = True
        self._state, self.speed_percent, self.reason = "FAULT_LATCHED", 0, str(reason)
        # No ARM/SPEED is ever retried. A bounded best-effort stop may fail too.
        try:
            self.link.write(b"\n" + self.encoder.stop())
        except Exception:
            pass

    def _command(self, frame, expected, duty):
        if self.failed:
            raise RuntimeError("USB session faulted; explicit close/reopen/reset required")
        try:
            if self.link.write(frame) != len(frame):
                raise RuntimeError("Partial serial write")
            sequence = self.encoder.last_sequence
            deadline = self.clock() + .12
            while self.clock() < deadline:
                status = self._read()
                if status is None:
                    self.wait(.001)
                    continue
                if status.sequence == 0 or status.reason == "BOOT":
                    raise RuntimeError("MCU reset during session")
                if status.sequence < sequence:
                    if status.state == "FAULT_LATCHED":
                        raise RuntimeError("MCU fault")
                    continue  # previously queued status, not an ACK for this command
                if status.sequence != sequence or status.state != expected or status.duty != duty:
                    raise RuntimeError(f"Unexpected MCU status: {status}")
                self._state, self.reason = status.state, status.reason
                return
            raise RuntimeError("Matching state not observed before deadline (status may have coalesced)")
        except Exception as error:
            self._trip(error)
            raise RuntimeError(str(error)) from error

    def disarm(self):
        self._command(self.encoder.disarm(), "DISARMED", 0)
        self.speed_percent = 0

    def arm(self):
        if self.state != "DISARMED":
            raise RuntimeError("Explicit DISARM required")
        self._command(self.encoder.arm(), "ARMED", 0)

    def set_speed(self, percent, *, expires_at=None):
        validate_percent(percent)
        if percent == 0:
            self.stop()
            return
        if self.state not in ("ARMED", "DRIVE"):
            raise RuntimeError("Not armed")
        self.tick()  # consume any asynchronous reset/fault before sending motion
        if self.buffer:
            self._trip("Incomplete asynchronous status before motion")
            raise RuntimeError(self.reason)
        if expires_at is not None and self.clock() >= expires_at:
            self.stop()
            raise RuntimeError("Speed observation expired before write")
        self._command(self.encoder.set_speed(percent), "DRIVE", (percent*255+50)//100)
        self.speed_percent = percent

    def stop(self):
        if self.failed or self.state == "BRAKE_LATCHED":
            return
        self._command(self.encoder.stop(), "BRAKE_LATCHED", 0)
        self.speed_percent = 0

    def tick(self):
        if self.failed:
            return
        try:
            for _ in range(8):
                status = self._read()
                if status is None:
                    return
                if status.sequence == 0 or status.reason == "BOOT" or status.state == "FAULT_LATCHED":
                    raise RuntimeError("MCU reset/fault; manual session recovery required")
                if status.sequence != self.encoder.last_sequence or status.state != self.state:
                    raise RuntimeError("Unexpected asynchronous status")
        except Exception as error:
            self._trip(error)
            raise RuntimeError(str(error)) from error

    def close(self):
        try:
            self.stop()
        finally:
            self.link.close()
