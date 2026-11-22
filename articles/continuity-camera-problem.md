# Why the Script Couldn't See My Face — The Continuity Camera Problem

When we first got the neck reminder working, it ran fine. Then the computer was restarted and suddenly the calibration step kept failing with: *"got 10 frames but no face detected."*

The camera green light was turning on. The frames were being read. The face was right there, well-lit, close to the camera. But MediaPipe saw nothing.

The screenshot told the full story. The macOS camera indicator showed **Muninder's iPhone Camera** — not the built-in FaceTime camera — with a completely black preview.

What happened: macOS has a feature called Continuity Camera that lets your iPhone act as a webcam over Wi-Fi. When your iPhone is nearby and the feature is enabled, macOS registers it as camera index 0 — the default. The built-in FaceTime camera gets pushed to index 1 or higher.

The script was opening `VideoCapture(0)` without checking which physical device that pointed to. The iPhone camera was registered but not actively streaming, so it returned valid-looking black frames. No face in a black frame — detection fails silently.

The fix had two parts. First, we added a brightness check: `frame.mean() > 1` rejects frames that are essentially black, so the camera scanner skips the dead iPhone feed automatically. Second, we added named camera arguments — `mac` to force the built-in FaceTime camera and `iphone` to intentionally use Continuity Camera — so the user always has explicit control regardless of what macOS decides is "default."

The lesson: on modern Macs, camera index 0 is not guaranteed to be the built-in camera. Always validate the frame, not just the connection.
