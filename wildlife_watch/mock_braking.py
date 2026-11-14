"""Mock-only actuation adapter. No serial connection or physical controller path."""

from time import perf_counter
from threading import Event, RLock, Thread
from functools import wraps

from .collision import CollisionPredictor, braking_policy, BrakeDecision
import math
from .hardware import MockCarController
from .tracking_loss import LossConfig, TrackingLoss


def synchronized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return call


class MockBrakingDemo:
    def __init__(self, collision_config, braking_config, clock=perf_counter, loss_config=None, serial_controller=None):
        self.lock = RLock()
        self.shutdown = Event()
        self.worker = None
        self.tracking = TrackingLoss(loss_config or LossConfig())
        self.last_callback = None
        self.clock = clock
        self.predictor = CollisionPredictor(collision_config)
        self.config = braking_config
        self.serial_mode = serial_controller is not None
        self.car = serial_controller if self.serial_mode else MockCarController(clock=clock)
        self.backend_label = self.car.backend_label if self.serial_mode else "MOCK ONLY"
        self.risk = self.predictor.update(None, clock())
        self.brake = self.decide_brake()
        self.message = "Press A to explicitly arm on fresh LOW risk"
        if hasattr(self.car, "diagnostic_context"):
            self.car.diagnostic_context = self.diagnostic_context

    def diagnostic_context(self):
        now = self.clock()
        pose = self.tracking.last_pose
        return dict(risk=self.risk.risk, risk_reason=self.risk.reason,
                    tracking=self.tracking.state,
                    observation_age_s=None if pose is None else now-pose.timestamp_s,
                    callback_age_s=None if self.last_callback is None else now-self.last_callback,
                    policy_reason=self.brake.reason)

    def stop(self, reason):
        if hasattr(self.car, "diagnostic_context"):
            self.car.stop(reason=reason)
        else:
            self.car.stop()

    @synchronized
    def observe(self, observation):
        self.last_callback = self.clock()
        self._process(observation)

    def decide_brake(self):
        return braking_policy(self.risk, self.config)

    def _process(self, observation, stop_trigger=None):
        now = self.clock()
        if observation is not None and now - observation.timestamp_s > self.tracking.config.capture_timeout_s:
            stop_trigger = "STALE_OBSERVATION"
            observation = None
        self.risk = self.predictor.update(observation, now)
        self.tracking.update(observation, self.risk, now)
        self.brake = self.decide_brake()
        speed_bound = getattr(self.car, "max_relative_speed_cm_s", None)
        if speed_bound is not None and self.risk.closing_speed_cm_s is not None:
            if math.hypot(self.risk.closing_speed_cm_s, self.risk.lateral_speed_cm_s or 0) > speed_bound:
                self.brake = BrakeDecision("STOP", 0, "MEASURED_SPEED_BOUND_EXCEEDED")
        if self.risk.risk == "UNKNOWN" and not self.serial_mode:
            self.brake = self.tracking.provisional(now, self.config.slow_duty)
        if self.brake.level == "STOP":
            trigger = stop_trigger or (
                "HIGH_RISK" if self.risk.risk == "HIGH" else
                "MARKER_LOSS" if observation is not None and not observation.detection_valid else
                "MISSING_OBSERVATION" if observation is None else
                "UNKNOWN_RISK" if self.risk.risk == "UNKNOWN" else self.brake.reason)
            self.stop(trigger)
        elif self.car.state in ("ARMED", "DRIVE"):
            if hasattr(self.car, "set_action"):
                self.car.set_action(self.brake.level,
                                    expires_at=observation.timestamp_s + self.tracking.config.capture_timeout_s)
                return
            # No automatic increase after slowing; deliberate re-arm grants it.
            duty = min(self.brake.duty_percent, self.car.speed_percent or self.brake.duty_percent)
            if self.serial_mode:
                self.car.set_speed(duty, expires_at=observation.timestamp_s + self.tracking.config.capture_timeout_s)
            else:
                self.car.set_speed(duty)

    @synchronized
    def tick(self):
        now = self.clock()
        if self.last_callback is None or now - self.last_callback >= self.tracking.config.capture_timeout_s:
            self._process(None, "NO_CAMERA_CALLBACK" if self.last_callback is None else "STALE_CAMERA_CALLBACK")
        self.car.tick()

    def start(self):
        if self.worker is not None:
            return
        def run():
            while not self.shutdown.wait(.01):
                try:
                    self.tick()
                except Exception:
                    with self.lock:
                        self.stop("FRESHNESS_WORKER_ERROR")
                        self.message = "Freshness worker failed: STOP latched"
                    return
        self.worker = Thread(target=run, daemon=True, name="mock-freshness")
        self.worker.start()

    def close(self):
        self.shutdown.set()
        if self.worker is not None:
            self.worker.join(timeout=1)
        with self.lock:
            if self.serial_mode:
                self.car.close()
            else:
                self.car.stop()

    @synchronized
    def key(self, key):
        self.tick()
        if key in (ord("s"), ord("S")):
            self.stop("MANUAL_STOP")
            self.message = "Operator STOP latched"
        elif key in (ord("a"), ord("A")):
            fresh = 0 <= self.clock() - self.risk.timestamp_s <= self.predictor.config.stale_s
            if fresh and self.risk.risk == "LOW" and self.brake.level == "NORMAL":
                # Both steps happen only in response to this operator action.
                self.car.disarm()
                self.car.arm()
                self.tracking.flicker_stop = False
                self.tracking.episodes.clear()
                self.message = "Explicitly armed; awaiting next fresh observation"
            else:
                self.message = "Arm denied: need fresh LOW + braking calibration"

    @synchronized
    def lines(self):
        self.tick()
        now = self.clock()
        history = self.tracking.history
        pose = self.tracking.last_pose
        pose_age = "--" if pose is None else f"{now-pose.timestamp_s:.3f}s"
        history_text = "none" if history is None else f"{history.risk}, age {now-self.tracking.history_time:.3f}s"
        conflict = "--" if self.risk.conflict_in_s is None else f"{self.risk.conflict_in_s:.2f}s"
        margin = "--" if self.brake.stopping_margin_cm is None else f"{self.brake.stopping_margin_cm:.1f} cm"
        return [f"{self.backend_label} | Risk {self.risk.risk} | Conflict in {conflict}",
                f"{self.tracking.state} | Observation age {pose_age}",
                f"HISTORICAL risk: {history_text}",
                "HISTORICAL pose: --" if pose is None else f"HISTORICAL Z {pose.distance_cm:.1f} X {pose.lateral_cm:.1f} cm",
                f"Risk reason: {self.risk.reason}",
                f"Policy {self.brake.level}: {self.brake.reason}",
                f"Requested {self.brake.duty_percent}% | Stopping margin {margin}",
                f"Controller {self.car.state} | Requested duty {self.car.speed_percent}%",
                "A: explicit arm/rearm | S: latched stop", self.message]
