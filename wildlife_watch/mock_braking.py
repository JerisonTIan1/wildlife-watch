"""Mock-only actuation adapter. No serial connection or physical controller path."""

from time import perf_counter
from threading import Event, RLock, Thread
from functools import wraps

from .collision import CollisionPredictor, braking_policy
from .hardware import MockCarController
from .tracking_loss import LossConfig, TrackingLoss


def synchronized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return call


class MockBrakingDemo:
    def __init__(self, collision_config, braking_config, clock=perf_counter, loss_config=None):
        self.lock = RLock()
        self.shutdown = Event()
        self.worker = None
        self.tracking = TrackingLoss(loss_config or LossConfig())
        self.last_callback = None
        self.clock = clock
        self.predictor = CollisionPredictor(collision_config)
        self.config = braking_config
        self.car = MockCarController(clock=clock)
        self.risk = self.predictor.update(None, clock())
        self.brake = braking_policy(self.risk, self.config)
        self.message = "Press A to explicitly arm on fresh LOW risk"

    @synchronized
    def observe(self, observation):
        self.last_callback = self.clock()
        self._process(observation)

    def _process(self, observation):
        now = self.clock()
        if observation is not None and now - observation.timestamp_s > self.tracking.config.capture_timeout_s:
            observation = None
        self.risk = self.predictor.update(observation, now)
        self.tracking.update(observation, self.risk, now)
        self.brake = braking_policy(self.risk, self.config)
        if self.risk.risk == "UNKNOWN":
            self.brake = self.tracking.provisional(now, self.config.slow_duty)
        if self.brake.level == "STOP":
            self.car.stop()
        elif self.car.state in ("ARMED", "DRIVE"):
            # No automatic increase after slowing; deliberate re-arm grants it.
            duty = min(self.brake.duty_percent, self.car.speed_percent or self.brake.duty_percent)
            self.car.set_speed(duty)

    @synchronized
    def tick(self):
        now = self.clock()
        if self.last_callback is None or now - self.last_callback >= self.tracking.config.capture_timeout_s:
            self._process(None)
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
                        self.car.stop()
                        self.message = "Freshness worker failed: STOP latched"
                    return
        self.worker = Thread(target=run, daemon=True, name="mock-freshness")
        self.worker.start()

    def close(self):
        self.shutdown.set()
        if self.worker is not None:
            self.worker.join(timeout=1)
        with self.lock:
            self.car.stop()

    @synchronized
    def key(self, key):
        self.tick()
        if key in (ord("s"), ord("S")):
            self.car.stop()
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
        return [f"MOCK ONLY | Risk {self.risk.risk} | Conflict in {conflict}",
                f"{self.tracking.state} | Observation age {pose_age}",
                f"HISTORICAL risk: {history_text}",
                "HISTORICAL pose: --" if pose is None else f"HISTORICAL Z {pose.distance_cm:.1f} X {pose.lateral_cm:.1f} cm",
                f"Risk reason: {self.risk.reason}",
                f"Policy {self.brake.level}: {self.brake.reason}",
                f"Requested {self.brake.duty_percent}% | Stopping margin {margin}",
                f"Mock {self.car.state} | Applied duty {self.car.speed_percent}%",
                "A: explicit arm/rearm | S: latched stop", self.message]
