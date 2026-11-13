"""Constant-relative-velocity marker conflict prediction; no camera or motor I/O."""

from collections import deque
from dataclasses import dataclass
import math

from .marker_pose import Observation


@dataclass(frozen=True)
class CollisionConfig:
    vehicle_width_cm: float
    camera_to_front_cm: float
    camera_to_rear_cm: float
    target_half_width_cm: float
    target_half_depth_cm: float
    margin_cm: float
    horizon_s: float = 3.0
    high_risk_s: float = 1.0
    stale_s: float = 0.25
    max_reprojection_px: float = 3.0

    def __post_init__(self):
        for name, value in vars(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if min(self.vehicle_width_cm, self.horizon_s, self.stale_s, self.max_reprojection_px) <= 0:
            raise ValueError("Width, horizon, freshness and quality limit must be positive")
        if self.high_risk_s > self.horizon_s:
            raise ValueError("High-risk threshold exceeds horizon")


@dataclass(frozen=True)
class RiskDecision:
    risk: str
    reason: str
    timestamp_s: float
    conflict: bool | None = None
    conflict_in_s: float | None = None
    lateral_speed_cm_s: float | None = None
    forward_clearance_cm: float | None = None
    closing_speed_cm_s: float | None = None


def interval(position, velocity, lower, upper):
    """Times at which a constant-velocity coordinate lies in a closed interval."""
    if abs(velocity) < 1e-9:
        return (-math.inf, math.inf) if lower <= position <= upper else (math.inf, -math.inf)
    a, b = (lower - position) / velocity, (upper - position) / velocity
    return min(a, b), max(a, b)


class CollisionPredictor:
    def __init__(self, config: CollisionConfig):
        self.config = config
        self.samples = deque(maxlen=30)
        self.last_timestamp = None

    def update(self, observation: Observation | None, now: float) -> RiskDecision:
        c = self.config

        def unknown(reason):
            self.samples.clear()
            return RiskDecision("UNKNOWN", reason, now)

        if not math.isfinite(now):
            raise ValueError("now must be a finite monotonic timestamp")
        if observation is None:
            return unknown("MISSING")
        o = observation
        if not math.isfinite(o.timestamp_s) or not 0 <= now - o.timestamp_s <= c.stale_s:
            return unknown("STALE_OR_FUTURE")
        if self.last_timestamp is not None and o.timestamp_s <= self.last_timestamp:
            return unknown("NONINCREASING_TIMESTAMP")
        self.last_timestamp = o.timestamp_s
        if not o.detection_valid or not o.pose_valid or o.marker_id != 0:
            return unknown("INVALID_OBSERVATION")
        values = (o.distance_cm, o.lateral_cm, o.reprojection_error_px)
        if any(v is None or not math.isfinite(v) for v in values):
            return unknown("MISSING_POSE_QUALITY")
        if o.distance_cm <= 0 or not 0 <= o.reprojection_error_px <= c.max_reprojection_px:
            return unknown("UNRELIABLE_POSE")
        half_width = c.vehicle_width_cm / 2 + c.target_half_width_cm + c.margin_cm
        front = c.camera_to_front_cm + c.target_half_depth_cm + c.margin_cm
        rear = -c.camera_to_rear_cm - c.target_half_depth_cm - c.margin_cm
        # Current geometric overlap is urgent even before velocity warms up.
        if abs(o.lateral_cm) <= half_width and rear <= o.distance_cm <= front:
            return RiskDecision("HIGH", "CURRENT_OVERLAP", now, True, 0.,
                                forward_clearance_cm=o.distance_cm-front,
                                closing_speed_cm_s=o.closing_speed_cm_s)
        if self.samples and o.timestamp_s - self.samples[-1][0] > c.stale_s:
            self.samples.clear()
        self.samples.append((o.timestamp_s, o.lateral_cm))
        while self.samples and o.timestamp_s - self.samples[0][0] > .3:
            self.samples.popleft()
        if o.closing_speed_cm_s is None or not math.isfinite(o.closing_speed_cm_s):
            return RiskDecision("UNKNOWN", "CLOSING_SPEED_UNAVAILABLE", now)
        if len(self.samples) < 3 or o.timestamp_s - self.samples[0][0] < .08:
            return RiskDecision("UNKNOWN", "LATERAL_WARMUP", now)
        mean_t = sum(t for t, _ in self.samples) / len(self.samples)
        mean_x = sum(x for _, x in self.samples) / len(self.samples)
        vx = sum((t-mean_t)*(x-mean_x) for t, x in self.samples) / sum((t-mean_t)**2 for t, _ in self.samples)
        age = now - o.timestamp_s
        x = o.lateral_cm + vx * age
        z = o.distance_cm - o.closing_speed_cm_s * age
        tx = interval(x, vx, -half_width, half_width)
        tz = interval(z, -o.closing_speed_cm_s, rear, front)
        entry = max(0., tx[0], tz[0])
        exit_time = min(c.horizon_s, tx[1], tz[1])
        conflict = entry <= exit_time
        risk = ("HIGH" if entry <= c.high_risk_s else "MEDIUM") if conflict else "LOW"
        return RiskDecision(risk, "PREDICTED_OVERLAP" if conflict else "NO_OVERLAP_WITHIN_HORIZON",
                            now, conflict, entry if conflict else None, vx, z-front, o.closing_speed_cm_s)


@dataclass(frozen=True)
class BrakingConfig:
    normal_duty: int
    slow_duty: int
    stopping_distance_cm: float | None = None
    response_delay_s: float | None = None

    def __post_init__(self):
        if any(type(v) is not int for v in (self.normal_duty, self.slow_duty)) or not 0 < self.slow_duty < self.normal_duty <= 100:
            raise ValueError("Require integer duties 0 < slow < normal <= 100")
        for value in (self.stopping_distance_cm, self.response_delay_s):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("Braking calibration must be finite and nonnegative")


@dataclass(frozen=True)
class BrakeDecision:
    level: str
    duty_percent: int
    reason: str
    stopping_margin_cm: float | None = None


def braking_policy(risk: RiskDecision, config: BrakingConfig) -> BrakeDecision:
    if risk.risk in ("UNKNOWN", "HIGH"):
        return BrakeDecision("STOP", 0, risk.risk)
    if config.stopping_distance_cm is None or config.response_delay_s is None:
        return BrakeDecision("STOP", 0, "BRAKING_CALIBRATION_UNAVAILABLE")
    margin = None
    if risk.conflict:
        margin = risk.forward_clearance_cm - config.stopping_distance_cm - max(0., risk.closing_speed_cm_s) * config.response_delay_s
        if margin <= 0:
            return BrakeDecision("STOP", 0, "STOPPING_MARGIN_EXHAUSTED", margin)
    if risk.risk == "MEDIUM":
        return BrakeDecision("SLOW", config.slow_duty, "PREDICTED_CONFLICT", margin)
    return BrakeDecision("NORMAL", config.normal_duty, "LOW_MODEL_RISK", margin)
