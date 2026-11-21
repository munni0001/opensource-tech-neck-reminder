#!/usr/bin/env python3
"""
neck_guard.py — beep + macOS notification when posture slips.

Usage:
  python neck_guard.py          # default 2-5 (watch 2min, rest 5min, repeat)
  python neck_guard.py 2-5
  python neck_guard.py 5-10

Detects:
  - Head tilt left/right (roll angle between eye corners)
  - Head coming forward  (face width > baseline × threshold)
"""

import cv2
import mediapipe as mp
import numpy as np
import subprocess
import sys
import time

# ── config ──────────────────────────────────────────────────────────────────
CHECK_EVERY_SEC     = 2.5   # seconds between posture checks (lower = more CPU)
TILT_THRESHOLD_DEG  = 12    # max head roll before it counts as bad (degrees)
FORWARD_THRESHOLD   = 1.25  # face width > baseline × this = head forward
GRACE_PERIOD_SEC    = 5     # must stay bad for this long before alerting
BEEP_COOLDOWN_SEC   = 15    # min seconds between consecutive beeps
CALIBRATE_SEC       = 4     # how long to hold good posture during setup
# ────────────────────────────────────────────────────────────────────────────

BEEP = ["afplay", "/System/Library/Sounds/Ping.aiff"]

_face = mp.solutions.face_mesh.FaceMesh(
    max_num_faces=1,
    static_image_mode=False,
    refine_landmarks=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)


def _fresh_frame(cap):
    """Flush camera buffer (up to 3 stale frames) and return a current one."""
    for _ in range(3):
        cap.grab()
    ok, frame = cap.read()
    return frame if ok else None


def _measure(frame):
    """
    Returns (roll_deg, face_width_px) or None if no face visible.
    roll_deg  — positive = tilted right, negative = tilted left
    face_width — inter-ocular distance in pixels; proxy for head-forward distance
    """
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = _face.process(rgb)
    if not res.multi_face_landmarks:
        return None
    lm = res.multi_face_landmarks[0].landmark
    h, w = frame.shape[:2]
    # outer eye corners: landmark 33 (viewer's left), 263 (viewer's right)
    p1 = np.array([lm[33].x * w, lm[33].y * h])
    p2 = np.array([lm[263].x * w, lm[263].y * h])
    dx, dy = p2 - p1
    roll = float(np.degrees(np.arctan2(dy, dx)))
    face_w = float(np.linalg.norm(p2 - p1))
    return roll, face_w


def _alert(msg):
    print(f"⚠  {msg}")
    subprocess.Popen(BEEP, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen(
        ["osascript", "-e", f'display notification "{msg}" with title "NeckGuard"'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _calibrate(cap):
    print(f"Calibrating — sit straight and look at the screen for {CALIBRATE_SEC}s ...")
    widths = []
    t0 = time.time()
    while time.time() - t0 < CALIBRATE_SEC:
        frame = _fresh_frame(cap)
        if frame is not None:
            m = _measure(frame)
            if m:
                widths.append(m[1])
        time.sleep(0.3)
    if not widths:
        print("ERROR: no face detected during calibration. Check your camera.")
        sys.exit(1)
    baseline = float(np.median(widths))
    print(f"Baseline set ({baseline:.0f}px). Watching every {CHECK_EVERY_SEC}s. Ctrl-C to quit.\n")
    return baseline


def _parse_cycle(arg):
    try:
        watch, rest = arg.split("-")
        return int(watch) * 60, int(rest) * 60
    except Exception:
        print(f"Bad format '{arg}'. Use WATCH-REST in minutes, e.g. 2-5")
        sys.exit(1)


def _open_camera():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    if not cap.isOpened():
        print("ERROR: cannot open camera.")
        sys.exit(1)
    return cap


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "2-5"
    watch_sec, rest_sec = _parse_cycle(arg)
    print(f"Cycle: watch {watch_sec//60}min → camera off {rest_sec//60}min → repeat")

    cap = _open_camera()
    baseline_w = _calibrate(cap)

    bad_since = None
    last_beep = 0.0

    try:
        while True:
            watch_until = time.time() + watch_sec
            print(f"Watching for {watch_sec//60}min ...")

            while time.time() < watch_until:
                frame = _fresh_frame(cap)
                now   = time.time()

                if frame is None:
                    time.sleep(CHECK_EVERY_SEC)
                    continue

                m = _measure(frame)
                if m is None:
                    bad_since = None
                    time.sleep(CHECK_EVERY_SEC)
                    continue

                roll, face_w = m
                issues = []

                if abs(roll) > TILT_THRESHOLD_DEG:
                    direction = "right" if roll > 0 else "left"
                    issues.append(f"head tilted {direction} ({roll:+.0f}°)")

                if face_w > baseline_w * FORWARD_THRESHOLD:
                    pct = int((face_w / baseline_w - 1) * 100)
                    issues.append(f"head forward (+{pct}%)")

                if issues:
                    if bad_since is None:
                        bad_since = now
                    elif (now - bad_since  >= GRACE_PERIOD_SEC and
                          now - last_beep  >= BEEP_COOLDOWN_SEC):
                        _alert(", ".join(issues))
                        last_beep = now
                        bad_since = now
                else:
                    if bad_since is not None:
                        print("✓ posture ok")
                    bad_since = None

                time.sleep(CHECK_EVERY_SEC)

            # rest — camera off
            cap.release()
            bad_since = None
            print(f"Camera off — resting {rest_sec//60}min ...")
            time.sleep(rest_sec)
            cap = _open_camera()
            print("Resuming ...")

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        cap.release()
        _face.close()


if __name__ == "__main__":
    main()
