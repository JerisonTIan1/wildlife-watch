"""Bounded mock-only loss policy. Historical data never becomes current risk."""

from collections import deque
from dataclasses import dataclass
import math

from .collision import BrakeDecision


@dataclass(frozen=True)
class LossConfig:
    grace_s: float = .15
    capture_timeout_s: float = .075
    measured_bounds: bool = False
    stopping_distance_bound_cm: float | None = None
    relative_speed_bound_cm_s: float | None = None
    latency_bound_s: float | None = None

    def __post_init__(self):
        if not math.isfinite(self.grace_s) or not 0 <= self.grace_s <= .5:
            raise ValueError("Mock grace must be 0..0.5 seconds")
        if not math.isfinite(self.capture_timeout_s) or not 0 < self.capture_timeout_s <= .15:
            raise ValueError("Capture timeout must be positive and <=150ms")
        if type(self.measured_bounds) is not bool:
            raise ValueError("measured_bounds must be boolean")
        for value in (self.stopping_distance_bound_cm, self.relative_speed_bound_cm_s, self.latency_bound_s):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError("Loss bounds must be finite and positive")


class TrackingLoss:
    def __init__(self, config):
        self.config = config
        self.last_pose = None
        self.history = None
        self.history_time = None
        self.state = "LOST"
        self.episode_start = None
        self.episodes = deque()
        self.flicker_stop = False

    def update(self, observation, risk, now):
        # Only predictor-accepted pose/warmup reasons may update pose history.
        accepted = observation is not None and (risk.risk != "UNKNOWN" or risk.reason in
                    ("LATERAL_WARMUP", "CLOSING_SPEED_UNAVAILABLE"))
        if accepted:
            self.last_pose = observation
        known = accepted and risk.risk != "UNKNOWN"
        if known:
            self.history, self.history_time = risk, observation.timestamp_s
            self.episode_start = None
            self.state = "TRACKED"
        else:
            if self.episode_start is None:
                # Deadline uses last known measurement, never first loss callback.
                self.episode_start = self.history_time if self.history_time is not None else now
                if self.history is not None:
                    self.episodes.append(now)
            while self.episodes and now - self.episodes[0] > 1.0:
                self.episodes.popleft()
            if len(self.episodes) >= 3:
                self.flicker_stop = True
            age = now - self.episode_start
            self.state = "TRACKED" if accepted else (
                "TEMPORARILY LOST" if self.history is not None and age < self.config.grace_s else "LOST")

    def provisional(self, now, slow_duty):
        c = self.config
        stop = lambda why: BrakeDecision("STOP", 0, why)
        if self.history is None or self.history.risk == "HIGH":
            return stop("NO_HISTORY_OR_LAST_HIGH")
        if self.flicker_stop:
            return stop("REPEATED_FLICKER")
        age = now - self.history_time
        if not 0 <= age < c.grace_s:
            return stop("LOSS_DEADLINE")
        bounds = (c.stopping_distance_bound_cm, c.relative_speed_bound_cm_s, c.latency_bound_s)
        if not c.measured_bounds or any(v is None for v in bounds):
            return stop("MEASURED_LOSS_BOUNDS_UNAVAILABLE")
        h = self.history
        if h.forward_clearance_cm is None or h.lateral_speed_cm_s is None or h.closing_speed_cm_s is None:
            return stop("HISTORY_INSUFFICIENT")
        if math.hypot(h.lateral_speed_cm_s, h.closing_speed_cm_s) > c.relative_speed_bound_cm_s:
            return stop("SPEED_BOUND_EXCEEDED")
        # Reserve travel for the FULL grace interval + bounded stop latency,
        # not a new grace interval at every missed/reacquired frame.
        margin = h.forward_clearance_cm - c.stopping_distance_bound_cm - c.relative_speed_bound_cm_s * (c.grace_s + c.latency_bound_s + .01)
        if margin <= 0:
            return stop("LOSS_STOPPING_MARGIN_EXHAUSTED")
        return BrakeDecision("SLOW", slow_duty, "PROVISIONAL_LOSS_REDUCTION", margin)
