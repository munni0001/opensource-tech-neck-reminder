# neck-reminder

A lightweight macOS tool that watches your posture via webcam and beeps when your head tilts or moves forward. No cloud, no account, runs entirely on your machine.

## What it detects

- Head tilting left or right
- Head moving forward (turtle neck)

## Requirements

- macOS
- Python 3.12
- Webcam

## Setup

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install numpy opencv-python absl-py flatbuffers certifi matplotlib sounddevice
pip install "mediapipe==0.10.21" --no-deps
```

## Run

```bash
python neck_guard.py          # default: watch 2min, camera off 5min, repeat
python neck_guard.py 2-5      # watch 2min, rest 5min
python neck_guard.py 5-10     # watch 5min, rest 10min
```

Sit straight during the 4-second calibration at startup. After that it runs quietly — beep + macOS notification when posture slips.

## Shortcut (optional)

Add to `~/.zshrc` to run from anywhere:

```zsh
function neckcare() {
    source /path/to/neck-care/venv/bin/activate
    python /path/to/neck-care/neck_guard.py "${1:-2-5}"
}
```

## Tune

Open `neck_guard.py` and edit the config block at the top:

| Setting | Default | What it does |
|---|---|---|
| `TILT_THRESHOLD_DEG` | 12 | Head tilt degrees before warning |
| `FORWARD_THRESHOLD` | 1.25 | Face must stay under this × baseline |
| `CHECK_EVERY_SEC` | 2.5 | How often to check (higher = less CPU) |
| `GRACE_PERIOD_SEC` | 5 | Seconds of bad posture before alert fires |
| `BEEP_COOLDOWN_SEC` | 15 | Minimum gap between alerts |

## Contributing

Issues and PRs welcome. Keep it simple — this is a single-file tool, not a framework. If you're adding detection (pitch, yaw, shoulder tracking) open an issue first so we can agree on approach before coding.

## License

MIT
