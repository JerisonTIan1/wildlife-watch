"""OpenCV-only presentation renderer; no prediction or control decisions."""
import math
import cv2
import numpy as np

RISK_COLORS = {"LOW": (110, 205, 95), "MEDIUM": (60, 185, 245),
               "HIGH": (85, 80, 240), "UNKNOWN": (155, 155, 155)}


def snapshot(demo, label):
    # Read existing calculated state atomically; never call controller actions here.
    with demo.lock:
        pose = demo.tracking.last_pose
        return dict(risk=demo.risk.risk, conflict=demo.risk.conflict_in_s,
                    policy=demo.brake.level, policy_duty=demo.brake.duty_percent,
                    controller=getattr(demo.car, "display_status", demo.car.state), duty=demo.car.speed_percent,
                    hardware=demo.backend_label, tracking=demo.tracking.state,
                    age=None if pose is None else demo.clock()-pose.timestamp_s,
                    label=label, message=(f"Request {demo.car.requested_action} PWM {demo.car.requested_pwm}/255 | ACK {demo.car.acknowledged_status}"
                                          if hasattr(demo.car, "acknowledged_status") else demo.message),
                    freshness_s=demo.tracking.config.capture_timeout_s)


def numeric(value, unit):
    return "--" if value is None or not math.isfinite(value) else f"{value:.1f} {unit}"


def current_metrics(observation, now, freshness_s):
    valid = (observation is not None and observation.pose_valid and observation.detection_valid
             and 0 <= now-observation.timestamp_s <= freshness_s)
    return (observation.distance_cm, observation.closing_speed_cm_s, observation.lateral_cm) if valid else (None, None, None)


def render(frame, observation, state, fps, now):
    """Fixed 1280x800 canvas; full camera frame letterboxed, never cropped/stretched."""
    state = state or {}
    canvas = np.full((800, 1280, 3), (23, 20, 18), np.uint8)
    white, muted = (235, 235, 235), (165, 162, 155)

    def text(value, x, y, scale=.55, color=white, width=1250):
        value = str(value)
        while value and cv2.getTextSize(value, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0][0] > width:
            scale *= .95
        cv2.putText(canvas, value, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)

    text("WILDCROSS", 24, 35, .85)
    text(state.get("hardware", "VISION ONLY - NO CONTROLLER"), 275, 32, .55, (230, 195, 100), 970)
    label = state.get("label", "Calibrated marker-assisted measurements" if observation else "Pixel-only view")
    warning = "SYNTHETIC" in label
    cv2.rectangle(canvas, (16, 48), (1264, 80), (42, 53, 69) if warning else (35, 32, 29), -1)
    text(label, 26, 70, .52, (80, 205, 255) if warning else muted)
    # Feed occupies 900x675, the majority of the dashboard.
    h, w = frame.shape[:2]
    scale = min(900/w, 675/h)
    dw, dh = max(1, round(w*scale)), max(1, round(h*scale))
    x, y = 16+(900-dw)//2, 92+(675-dh)//2
    canvas[y:y+dh, x:x+dw] = cv2.resize(frame, (dw, dh), interpolation=cv2.INTER_LINEAR)
    cv2.rectangle(canvas, (932, 92), (1264, 767), (34, 30, 27), -1)
    risk = state.get("risk", "UNKNOWN")
    color = RISK_COLORS.get(risk, RISK_COLORS["UNKNOWN"])
    cv2.circle(canvas, (1242, 117), 5, color, -1)
    text("COLLISION RISK", 952, 122, .45, muted)
    text(risk, 952, 159, .95, color, 285)
    values = current_metrics(observation, now, state.get("freshness_s", .25))
    for i, (name, value, unit) in enumerate(zip(("FORWARD DISTANCE", "RELATIVE CLOSING SPEED", "LATERAL OFFSET"), values, ("cm", "cm/s", "cm"))):
        top = 200+i*79
        text(name, 952, top, .43, muted, 290)
        text(numeric(value, unit), 952, top+34, .85, white, 290)
    text("PREDICTED TIME TO CONFLICT", 952, 437, .42, muted, 290)
    text(numeric(state.get("conflict") if risk != "UNKNOWN" else None, "s"), 952, 470, .8)
    text("BRAKING POLICY", 952, 508, .43, muted)
    text(f"{state.get('policy', '--')} / {state.get('policy_duty', '--')}% requested", 952, 535, .55, white, 290)
    text("ACTUAL CONTROLLER STATE", 952, 571, .43, muted)
    text(state.get("controller", "UNAVAILABLE"), 952, 597, .55, white, 290)
    duty = state.get('duty')
    text("Controller duty: " + ("--" if duty is None else f"{duty:.1f}%"), 952, 624, .52, muted, 290)
    text("Duty is a request, not measured speed", 952, 646, .36, muted, 290)
    text(state.get("tracking", "TRACKED" if observation and observation.pose_valid else "LOST"), 952, 685, .55, white, 290)
    age = state.get("age")
    if age is None and observation is not None:
        age = now-observation.timestamp_s
    text("Observation age: " + ("--" if age is None else f"{age*1000:.0f} ms"), 952, 710, .47, muted, 290)
    text(f"Observed FPS {fps:.1f}", 952, 746, .47, muted)
    text("A  ARM / REARM     S  STOP     Q / ESC  EXIT", 24, 789, .5)
    text(state.get("message", ""), 650, 789, .4, muted, 600)
    return canvas
