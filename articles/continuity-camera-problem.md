# Why the Script Couldn't See My Face — The Continuity Camera Problem

When we first got the neck reminder working, it ran fine. Then the computer was restarted and suddenly the calibration step kept failing with: *"got 10 frames but no face detected."*

The camera green light was turning on. The frames were being read. The face was right there, well-lit, close to the camera. But MediaPipe saw nothing.

The macOS camera indicator told the story. It showed **Muninder's iPhone Camera** — not the built-in FaceTime camera — with a completely black preview.

## What Happened

macOS has a feature called Continuity Camera that lets your iPhone act as a webcam over Wi-Fi. When your iPhone is nearby and the feature is enabled, macOS registers it as camera index 0 — the default — at the AVFoundation driver level. The built-in FaceTime camera gets pushed to index 1 or higher.

The script was opening `VideoCapture(0)` without checking which physical device that pointed to. The iPhone camera was registered but not actively streaming (screen off, face-down on the desk), so it returned valid-looking black frames. No face in a black frame — detection fails silently with no useful error.

## First Attempt: Brightness Check

The first fix was adding `frame.mean() > 1` to skip frames that are essentially black. The logic: if the iPhone isn't streaming, its frames are black and will be rejected. The scanner would then move to index 1 and find the FaceTime camera.

This worked — until the iPhone happened to be unlocked and streaming. When it was, `frame.mean()` passed but face detection still failed because the iPhone camera was pointed at the ceiling, not at the person.

## Second Attempt: system_profiler Name Lookup

The next attempt used `system_profiler SPCameraDataType -json` to query macOS for camera names and find the one containing "FaceTime":

```
Cameras found: ['FaceTime HD Camera', "Muninder's iPhone Camera"]
Using built-in camera: 'FaceTime HD Camera' (index 0)
```

Looks correct — except it wasn't. `system_profiler` listed FaceTime at index 0, but OpenCV's `VideoCapture(0)` still opened the iPhone. The two orderings don't match. macOS inserts the Continuity Camera at index 0 at a lower level than what `system_profiler` reports. The name lookup was returning the wrong index and the error changed from "no face detected" to "no working camera found."

## What Actually Fixed It: Face Detection During Camera Selection

The real fix was to stop guessing which index is which, and instead let MediaPipe decide. During camera startup, the script now scans each index in order, grabs a frame from each, and runs face detection on it. The camera that actually sees a face wins:

```python
if _measure(frame) is not None:
    print(f"Camera index {idx} active (face detected).")
    return cap
```

A quick scan confirmed what was happening the whole time:

```
index 0: mean=0.1, face=False   ← iPhone, black frame
index 1: mean=122.3, face=True  ← FaceTime HD Camera
```

Index 1 had a face. Index 0 did not. No name lookup, no index assumptions — just empirical detection. If the user is sitting in front of the camera when the script starts (which they always are, since calibration requires it), this is completely reliable.

The `mac` and `iphone` named arguments still exist for explicit control, but `mac` now means "auto-detect via face scan" rather than "look up by name." The `iphone` argument hard-codes index 0 since Continuity Camera is always there on macOS.

## The Lesson

On modern Macs with Continuity Camera enabled, camera index 0 is not guaranteed to be the built-in camera — and the system's own camera listing tool doesn't reflect the same ordering that OpenCV uses. The only reliable way to find the right camera is to validate what comes out of it, not which slot it sits in.
