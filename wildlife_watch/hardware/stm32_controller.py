"""NUCLEO ASCII transport, wheels-raised only. No V1 commands or automatic replay."""
from time import perf_counter, sleep
import math
import json
import logging

LOG = logging.getLogger("wildlife_watch.motor_diagnostics")


def validate_bench_config(data, brakes, normal_pwm, slow_pwm):
    """Reject unmeasured configs before opening any COM port. Attestation, not metrology."""
    if data.get("synthetic") is not False:
        raise ValueError("STM32 physical actuation forbids synthetic configuration")
    if any(type(v) is not int for v in (normal_pwm, slow_pwm)) or not 0 < slow_pwm < normal_pwm <= 255:
        raise ValueError("Invalid STM32 PWM mapping")
    measured = data.get("stm32_bench_measurements", {})
    if any(measured.get(name) is not True for name in
           ("vehicle_and_target_geometry_measured", "coast_stopping_measured", "latency_measured")):
        raise ValueError("Measured vehicle/target geometry, coast stopping and latency attestations are required")
    for name in ("max_relative_speed_cm_s", "max_pwm_tested"):
        value = measured.get(name)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Missing measured {name}")
    if not normal_pwm <= measured["max_pwm_tested"] <= 255:
        raise ValueError("Requested PWM exceeds measured operating envelope")
    if any(v is None or not math.isfinite(v) or v <= 0 for v in
           (brakes.stopping_distance_cm, brakes.response_delay_s)):
        raise ValueError("Positive measured coast stopping distance and latency required")
    if brakes.response_delay_s < .18:
        raise ValueError("Latency must cover at least 50ms write + 120ms ACK + 10ms monitor, plus measured upstream delay")
    from pathlib import Path
    record = measured.get("measurement_record")
    if not isinstance(record, str) or not record.strip() or not Path(record).is_file() or not Path(record).read_text(encoding="utf-8").strip():
        raise ValueError("A nonempty measurement_record file is required; do not copy example values")


class STM32Controller:
    backend_label = "REAL STM32 USB / WHEELS RAISED / STOP = COAST"

    def __init__(self, port, *, normal_pwm=120, slow_pwm=80, serial_factory=None,
                 clock=perf_counter, wait=sleep):
        if any(type(v) is not int for v in (normal_pwm, slow_pwm)) or not 0 < slow_pwm < normal_pwm <= 255:
            raise ValueError("Require integer PWM 0 < slow < normal <= 255")
        if serial_factory is None:
            import serial
            serial_factory = serial.Serial
        self.clock, self.wait = clock, wait
        self.normal_pwm, self.slow_pwm = normal_pwm, slow_pwm
        self.state = "DISARMED"
        self.failed = False
        self.requested_action = "STOP"
        self.requested_pwm = 0
        self.acknowledged_pwm = None
        self.acknowledged_status = "UNKNOWN"
        self.last_motion = float("-inf")
        self.last_expiry = None
        self.last_pwm_sent = None
        self.last_pwm_sent_at = None
        self.diagnostic_context = lambda: {}
        self.buffer = bytearray()
        self.link = serial_factory(port=port, baudrate=115200, timeout=0, write_timeout=.05)
        try:
            self.link.reset_input_buffer()
            self.diagnostic("STOP", "STARTUP")
            self._exchange(b"STOP\n", "STOPPED")
        except Exception:
            self.link.close()
            raise

    @property
    def speed_percent(self):
        # Acknowledged PWM request only, never measured motor speed.
        return None if self.acknowledged_pwm is None else self.acknowledged_pwm * 100 / 255

    def diagnostic(self, event, trigger, **details):
        if not LOG.isEnabledFor(logging.INFO):
            return
        # Diagnostics must never prevent a safety action, even if a sink fails.
        try:
            now = self.clock()
            LOG.info(json.dumps(dict(t_s=now, event=event, trigger=trigger,
                controller_state=self.state, last_pwm=self.last_pwm_sent,
                since_motor_command_s=None if self.last_pwm_sent_at is None else now-self.last_pwm_sent_at,
                last_ack=self.acknowledged_status, **self.diagnostic_context(), **details)))
        except Exception:
            pass

    @property
    def display_status(self):
        return f"{self.state} / ACK {self.acknowledged_status}"

    def _line(self):
        for _ in range(16):
            if b"\n" in self.buffer:
                break
            data = self.link.read(128)
            if not data:
                break
            self.buffer.extend(data)
        if len(self.buffer) > 512:
            raise RuntimeError("Oversized STM32 reply")
        if b"\n" not in self.buffer:
            return None
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        return line.decode("ascii").strip()

    def _trip(self, error):
        message = str(error)
        trigger = ("FIRMWARE_TIMEOUT" if "TIMEOUT - STOPPED" in message else
                   "MISSING_ACK" if "acknowledgement timeout" in message else "SERIAL_ERROR")
        self.diagnostic("STOP", trigger, error=message)
        self.failed, self.state = True, "FAULT_LATCHED"
        self.requested_action, self.requested_pwm = "STOP", 0
        self.acknowledged_status, self.acknowledged_pwm = "UNKNOWN", None
        self.reason = str(error)
        try:
            self.link.write(b"\nSTOP\n")  # terminate any partial numeric frame, then stop
        except Exception:
            pass

    def _exchange(self, command, expected):
        if self.failed:
            raise RuntimeError("STM32 session faulted; no automatic reconnect/rearm")
        try:
            if command.strip().isdigit():
                self.last_pwm_sent = int(command.strip())
                self.last_pwm_sent_at = self.clock()
            self.diagnostic("TX", "SERIAL_WRITE", command=command.decode().strip())
            if self.link.write(command) != len(command):
                raise RuntimeError("Partial STM32 write")
            until = self.clock() + .12
            while self.clock() < until:
                line = self._line()
                if line is None:
                    self.wait(.001)
                    continue
                if line != expected:
                    raise RuntimeError(f"Unexpected STM32 reply: {line!r}")
                self.acknowledged_status = line
                self.acknowledged_pwm = 0 if line == "STOPPED" else int(line.split("=")[1])
                self.diagnostic("ACK", "SERIAL_ACK", reply=line)
                return
            raise RuntimeError("STM32 acknowledgement timeout")
        except Exception as error:
            self._trip(error)
            raise RuntimeError(str(error)) from error

    def stop(self, force=False, *, reason="STOP_REQUEST"):
        if not self.failed and (force or self.state != "BRAKE_LATCHED"):
            self.diagnostic("STOP", reason)
        self.requested_action, self.requested_pwm = "STOP", 0
        if self.failed:
            return
        if force or self.state != "BRAKE_LATCHED":
            self._exchange(b"STOP\n", "STOPPED")
        self.state = "BRAKE_LATCHED"  # host latch; board itself has no ARM command
        self.last_expiry = None

    def disarm(self):
        if self.failed:
            raise RuntimeError("Faulted STM32 session")
        self.stop(force=True, reason="OPERATOR_DISARM_BEFORE_ARM")
        self.state = "DISARMED"

    def arm(self):
        if self.failed or self.state != "DISARMED":
            raise RuntimeError("Explicit disarm required before host arm")
        self.tick()
        self.state = "ARMED"  # no bytes and no PWM on arm
        self.diagnostic("ARM", "MANUAL_ARM")

    def set_action(self, action, *, expires_at):
        if not math.isfinite(expires_at):
            self.stop(reason="INVALID_FRESHNESS_DEADLINE")
            raise ValueError("Freshness deadline must be finite")
        if action == "STOP":
            self.stop(reason="EXPLICIT_STOP_ACTION")
            return
        if action not in ("NORMAL", "SLOW") or self.failed or self.state not in ("ARMED", "DRIVE"):
            raise RuntimeError("Motion not permitted")
        self.tick()
        if self.state not in ("ARMED", "DRIVE") or self.clock() >= expires_at:
            self.stop(reason="OBSERVATION_EXPIRED_BEFORE_COMMAND")
            return
        pwm = self.normal_pwm if action == "NORMAL" else self.slow_pwm
        if self.state == "DRIVE":
            pwm = min(pwm, self.requested_pwm)  # never automatically accelerate after SLOW
        # At most 10 Hz for same/increasing duty; reductions and STOP are immediate.
        if self.clock()-self.last_motion < .1 and pwm >= self.requested_pwm and self.state == "DRIVE":
            self.last_expiry = expires_at  # fresh observation, not a cached motion replay
            return
        self.requested_action = "NORMAL" if pwm == self.normal_pwm else "SLOW"
        self.requested_pwm = pwm
        self._exchange(f"{pwm}\n".encode("ascii"), f"PWM = {pwm}")
        self.state = "DRIVE"
        self.last_motion = self.clock()
        self.last_expiry = expires_at
        if self.clock() >= expires_at:
            self.stop(reason="OBSERVATION_EXPIRED_DURING_ACK")

    def tick(self):
        if self.failed:
            return
        try:
            line = self._line()
            if line is not None or self.buffer:
                raise RuntimeError(f"Unexpected asynchronous STM32 status/reset: {line!r}")
            if self.state == "DRIVE" and self.last_expiry is not None and self.clock() >= self.last_expiry:
                self.stop(reason="CONTROLLER_WATCHDOG")
        except Exception as error:
            self._trip(error)
            raise RuntimeError(str(error)) from error

    def close(self):
        try:
            if self.failed:
                self._trip("Shutdown after fault")
            else:
                self.stop(force=True, reason="SHUTDOWN")
        finally:
            self.link.close()
