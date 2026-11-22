#!/usr/bin/env python3
"""
neck_guard.py — beep + macOS notification when posture slips.

Usage:
  python neck_guard.py          # default 2-5, auto-detect camera
  python neck_guard.py 2-5
  python neck_guard.py 2-5 mac      # force built-in FaceTime camera
  python neck_guard.py 2-5 iphone   # force iPhone Continuity Camera
  python neck_guard.py 2-5 1        # force by index number

Detects:
  - Head tilt left/right  (roll angle between eye corners)
  - Head coming forward   (face width > baseline × FORWARD_THRESHOLD)
  - Chin down / slouching (pitch ratio > baseline × CHIN_DOWN_THRESHOLD)
  - Chin up / head back   (pitch ratio < baseline × CHIN_UP_THRESHOLD)
"""

import cv2
import json
import mediapipe as mp
import numpy as np
import subprocess
import sys
import time

# ── config ──────────────────────────────────────────────────────────────────
CHECK_EVERY_SEC     = 2.5   # seconds between posture checks (lower = more CPU)
TILT_THRESHOLD_DEG  = 12    # max head roll before it counts as bad (degrees)
FORWARD_THRESHOLD   = 1.15  # face width > baseline × this = head forward
CHIN_DOWN_THRESHOLD = 1.20  # pitch ratio > baseline × this = chin dropped / slouching
CHIN_UP_THRESHOLD   = 0.85  # pitch ratio < baseline × this = chin raised / head back
GRACE_PERIOD_SEC    = 5     # bad posture must persist this long before first alert
REPEAT_BEEP_SEC     = 8     # keep alerting this often while posture stays bad
USE_VOICE           = True  # speak the alert out loud via macOS say
VOICE_MSG           = "Don't slouch"
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
    Returns (roll_deg, face_width_px, pitch_ratio) or None if no face visible.
    roll_deg    — positive = tilted right, negative = tilted left
    face_width  — inter-ocular distance in pixels; proxy for head-forward distance
    pitch_ratio — (nose_y - eye_y) / face_width; rises when chin drops, falls when chin lifts
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
    roll      = float(np.degrees(np.arctan2(dy, dx)))
    face_w    = float(np.linalg.norm(p2 - p1))
    eye_y     = (p1[1] + p2[1]) / 2
    nose_y    = lm[1].y * h
    pitch_ratio = (nose_y - eye_y) / face_w   # normalised by face width so distance-invariant
    return roll, face_w, pitch_ratio


def _alert(issues, first=False):
    msg = ", ".join(issues)
    print(f"⚠  {msg}")
    subprocess.Popen(BEEP, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if USE_VOICE:
        subprocess.Popen(["say", VOICE_MSG], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if first:   # notification only on first alert per episode — not every repeat
        subprocess.Popen(
            ["osascript", "-e", f'display notification "{msg}" with title "NeckGuard"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def _calibrate(cap):
    print(f"Calibrating — sit straight and look at the screen for {CALIBRATE_SEC}s ...")
    widths, pitches = [], []
    frames_read = 0
    t0 = time.time()
    while time.time() - t0 < CALIBRATE_SEC:
        frame = _fresh_frame(cap)
        if frame is not None:
            frames_read += 1
            m = _measure(frame)
            if m:
                widths.append(m[1])
                pitches.append(m[2])
        time.sleep(0.3)
    if not widths:
        if frames_read == 0:
            print("ERROR: camera not sending frames. Try unplugging/replugging.")
        else:
            print(f"ERROR: got {frames_read} frames but no face detected — make sure your face is in frame and well-lit.")
        sys.exit(1)
    baseline_w = float(np.median(widths))
    baseline_p = float(np.median(pitches))
    print(f"Baseline set (face {baseline_w:.0f}px, pitch {baseline_p:.2f}). Watching every {CHECK_EVERY_SEC}s. Ctrl-C to quit.\n")
    return baseline_w, baseline_p


def _camera_names():
    """Ask macOS for the camera list in AVFoundation order (matches OpenCV indices)."""
    try:
        out = subprocess.run(
            ["system_profiler", "SPCameraDataType", "-json"],
            capture_output=True, text=True, timeout=5
        ).stdout
        return [c.get("_name", "") for c in json.loads(out).get("SPCameraDataType", [])]
    except Exception:
        return []


def _resolve_camera(arg):
    lower = arg.lower()
    names = _camera_names()
    if names:
        print(f"Cameras found: {names}")

    if lower in ("mac", "facetime", "builtin"):
        for i, name in enumerate(names):
            if any(k in name.lower() for k in ("facetime", "built-in", "isight")):
                print(f"Using built-in camera: '{name}' (index {i})")
                return i
        print("Built-in camera not found by name, falling back to auto-detect.")
        return None

    if lower in ("iphone", "continuity"):
        for i, name in enumerate(names):
            if any(k in name.lower() for k in ("iphone", "continuity", "external")):
                print(f"Using iPhone camera: '{name}' (index {i})")
                return i
        print("iPhone camera not found by name, falling back to index 0.")
        return 0

    try:
        return int(arg)
    except ValueError:
        print(f"Unknown camera '{arg}'. Use: mac, iphone, or a number (0, 1, 2 …)")
        sys.exit(1)


def _parse_cycle(arg):
    try:
        watch, rest = arg.split("-")
        return int(watch) * 60, int(rest) * 60
    except Exception:
        print(f"Bad format '{arg}'. Use WATCH-REST in minutes, e.g. 2-5")
        sys.exit(1)


def _open_camera(forced_idx=None):
    indices = [forced_idx] if forced_idx is not None else range(4)
    fallback = None   # first camera with a bright frame but no face yet

    for idx in indices:
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        for _ in range(20):   # let sensor warm up
            cap.grab()
        ok, frame = cap.read()
        if not (ok and frame is not None and frame.size > 0 and frame.mean() > 1):
            cap.release()
            continue
        # Try face detection — built-in camera sees you, iPhone usually won't
        if _measure(frame) is not None:
            print(f"Camera index {idx} active (face detected).")
            if fallback:
                fallback.release()
            return cap
        if fallback is None:
            fallback = cap
        else:
            cap.release()

    if fallback:
        print("Camera active (no face detected during selection — sit in front of camera before starting).")
        return fallback

    print("ERROR: no working camera found.")
    sys.exit(1)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "2-5"
    cam_idx = _resolve_camera(sys.argv[2]) if len(sys.argv) > 2 else _resolve_camera("mac")
    watch_sec, rest_sec = _parse_cycle(arg)
    print(f"Cycle: watch {watch_sec//60}min → camera off {rest_sec//60}min → repeat")

    cap = _open_camera(cam_idx)
    baseline_w, baseline_p = _calibrate(cap)

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

                roll, face_w, pitch = m
                issues = []

                if abs(roll) > TILT_THRESHOLD_DEG:
                    direction = "right" if roll > 0 else "left"
                    issues.append(f"head tilted {direction} ({roll:+.0f}°)")

                if face_w > baseline_w * FORWARD_THRESHOLD:
                    pct = int((face_w / baseline_w - 1) * 100)
                    issues.append(f"head forward (+{pct}%)")

                if pitch > baseline_p * CHIN_DOWN_THRESHOLD:
                    issues.append("chin down / slouching")

                if pitch < baseline_p * CHIN_UP_THRESHOLD:
                    issues.append("chin up / head back")

                if issues:
                    if bad_since is None:
                        bad_since = now
                    elif now - bad_since >= GRACE_PERIOD_SEC:
                        first_alert = last_beep == 0.0
                        if now - last_beep >= REPEAT_BEEP_SEC:
                            _alert(issues, first=first_alert)
                            last_beep = now
                else:
                    if bad_since is not None:
                        print("✓ posture ok")
                        last_beep = 0.0   # reset so next episode starts fresh
                    bad_since = None

                time.sleep(CHECK_EVERY_SEC)

            # rest — camera off
            cap.release()
            bad_since = None
            print(f"Camera off — resting {rest_sec//60}min ...")
            time.sleep(rest_sec)
            cap = _open_camera(cam_idx)
            print("Resuming ...")

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        cap.release()
        _face.close()


if __name__ == "__main__":
    main()
