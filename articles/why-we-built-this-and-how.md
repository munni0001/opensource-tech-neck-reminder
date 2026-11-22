# From Automator Scripts to MediaPipe — Building a Neck Posture Reminder That Actually Works on macOS

## The Problem

Sitting at a desk for hours does something gradual and predictable. The head drifts forward. The chin drops. The shoulders round inward. By the time you notice, your neck has been held in a bad angle for 45 minutes and there's a dull ache starting at the base of the skull.

The goal was simple: something that watches while you work and nudges you back to good posture before the damage accumulates. Not an app to subscribe to. Not something that requires a phone. Just a quiet, local tool on the Mac that notices when the head is coming forward or tilting sideways and makes a sound.

## What We Tried First

The first instinct is always to look for something that already exists. macOS has several built-in automation tools — Automator, AppleScript, Shortcuts — and the App Store has posture apps. The problems compound quickly.

Commercial apps like Posture Reminder or Uprright use the camera continuously with no control over when it runs. Battery drain is noticeable. Privacy is a concern. You have no idea what the frames are being used for beyond what the marketing copy says.

Automator and Shortcuts can run scripts on a schedule, but they have no access to the camera or any image processing. You can build a time-based reminder — "sit straight" every 30 minutes — but that's a clock, not a posture detector. It fires whether you're slouching or not.

AppleScript overlays and notification banners can interrupt your screen, but again, without detection behind them they're just annoying random alerts you start ignoring within two days.

The pattern with all of these is the same: either they're too dumb (time-based, no detection), too intrusive (commercial apps that want to run all the time), or not built for this purpose at all (Automator doing something it was never designed to do).

## Why Python and MediaPipe

The requirement was clear once we stopped looking for existing tools: we needed a camera feed, real-time face landmark detection, and control over exactly when the camera is on. That pointed directly to computer vision.

The two main options were OpenCV with dlib, or MediaPipe Face Mesh. Dlib requires compiling C++ dependencies and is heavier. MediaPipe is open source (Apache 2.0), ships as a Python wheel, runs entirely on CPU with no GPU requirement, and its Face Mesh model gives 468 landmarks per face — far more than needed, but it means the geometry we care about (eye corners for roll, nose position for pitch and forward lean) is immediately available with no extra work.

The detection logic is built on three measurements, all derived from the landmark coordinates:

**Roll (head tilt):** The angle of the line connecting the two outer eye corners. When the head tilts left or right, this angle changes. Simple trigonometry — `arctan2(dy, dx)` — gives the degrees of tilt directly.

**Forward lean (turtle neck):** The inter-ocular distance in pixels. When the head moves toward the camera, the face appears larger. Calibrating this distance at startup gives a personal baseline; if the face gets 15% wider than baseline during a session, the head has moved forward.

**Pitch (chin up or down):** The vertical distance from the eye line to the nose tip, normalised by the inter-ocular distance so it stays consistent regardless of how far the face is from the camera. When the chin drops (slouching, looking at a phone), this ratio rises. When the chin lifts (head tilting back), it falls.

## The Watch-Rest Cycle

Keeping the camera on continuously was always going to be a problem — practically and psychologically. The green light on the camera is on all the time. It draws battery even when you're not at the desk. And it's unsettling.

The solution was a watch-rest cycle. The script runs the camera for N minutes, then releases it completely for M minutes, then resumes. During the rest period the green light is off. You can run `neckcare 2-5` for a 2-minute watch / 5-minute rest cycle, or `neckcare 5-10` if you want less frequent checks.

This design also has a training effect. The goal was never to have an app running forever. It's to build the habit. After a few weeks of being corrected regularly, you start self-correcting before the beep fires. At that point you can extend the rest period or stop running it at all.

## The Setup That Stuck

The final setup is a single Python file, a virtual environment with three dependencies (MediaPipe, OpenCV, NumPy), and a shell function in `.zshrc` so you can type `neckcare 2-5` from anywhere.

```
neck_guard.py        — the whole thing, ~200 lines
requirements.txt     — mediapipe==0.10.21, opencv-python, numpy
venv/                — Python 3.12 (3.14 has no prebuilt OpenCV wheel yet)
```

No background service. No launch agent. No subscription. No data leaving the machine. The camera runs for 2 minutes at a time, checks posture every 2.5 seconds, fires a beep and a macOS notification if bad posture has been held for 5 consecutive seconds, then goes quiet for 5 minutes.

The config block at the top of the file has six variables. Changing `FORWARD_THRESHOLD` from `1.25` to `1.15` was the difference between catching a 25% forward lean and catching a 15% one — a real-world difference in whether the alert fires before or after you've already noticed you're slouching.

## What It Doesn't Do

Worth being honest about the limits. The laptop camera is front-facing and narrow-angle. It cannot reliably see shoulder position, so true slouch detection (rounded shoulders) isn't there — head-forward is the proxy. Yaw detection (head turned sideways for a second monitor) is geometrically possible but hasn't been implemented yet.

It also doesn't survive closing the terminal. If you close the window that launched `neckcare`, the script stops. The fix is to run it inside tmux, which keeps it alive across terminal sessions. That's one open task.

## Why Open Source

There's nothing proprietary here. The approach is straightforward, the dependencies are all Apache 2.0 or BSD, and the code is short enough that anyone with a Mac and ten minutes can read the whole thing. If it helps someone else sit straighter at their desk, that's the point.

The repository is at [github.com/munni0001/opensource-tech-neck-reminder](https://github.com/munni0001/opensource-tech-neck-reminder).
