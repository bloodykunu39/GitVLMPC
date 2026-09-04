# GitVLMPC - Release v1.0.0

**September 5, 2026**

---

Shipping the public release of **GitVLMPC**, a lightweight, high-performance Windows desktop app that tracks your lecture video progress in real time while you watch in **MPC-BE** or **VLC Media Player**.

No database, no server, no subscriptions — just a portable standalone executable (`dist/GitVLMPC.exe`) or Python script and a single JSON data file that lives right beside your videos.

---

## What's in this Release

### Real-Time Lecture Tracking
- **Dual Media Player Support**: Real-time integration with MPC-BE (port `13579`) and VLC (port `8080`), featuring smart auto-detection and priority preferences.
- **Furthest-Position Tracking**: Automatically tracks the furthest watched timestamp, progress percentages, covered duration, and remaining time.
- **Color-Coded Statuses**: Clear visual distinctions for Watched (green), In-Progress (yellow), and Unwatched (red).
- **Ratings & Multiline Reviews**: 1–5 star ratings with 0.5-step wheel adjustments and review notes.
- **Visual Analytics**: Interactive Pie and Bar charts for study time distribution and rating metrics.

### Study Stopwatch & Session Management
- **Digital Study Stopwatch**: High-precision stopwatch with Start, Pause, and End controls.
- **Auto-Pause on Video Playback**: Automatically pauses your study session when the media player pauses or stops, and automatically resumes when video playback starts.
- **Study Session Logs**: Comprehensive historical activity table logging sessions, lectures, and video-playing durations.
- **Stopwatch Time Badge Right-Click Menu**: Quick manual time adjustments (`+15m`, `+5m`, `-5m`, `-15m`), clipboard copy, and auto-pause toggling.

### Focus Sound Engine & Study Reminders
- **Binaural Beats Generator**: Pure sinusoidal wave audio with independent Left and Right channel frequencies (Theta 4 Hz, Alpha 10 Hz, Beta 18 Hz, Delta 2 Hz, Gamma 40 Hz presets) for deep focus and flow states.
- **Custom MP3 Audio Playback**: Option to use personal audio files as study interval cues.
- **Live Reminder Countdown**: Configurable countdown badge displaying remaining time until next break cue.
- **Instant Visual Indicators**: Play button lights up in vibrant emerald green (`🔊 Playing ●`) when audio is active, and Pause in active crimson red (`⏸ Pause`), with zero click latency.
- **Interactive Mousewheel Scroller**: Smooth, segment-specific `HH : MM : SS` adjustment boxes with wrapping.
- **Inline Floating Panel**: Quick-add presets panel placed directly to the right side of the timer control without popup windows.
- **Activity Tagging & Reordering**: Assign tags (`☕ Break`, `🧘 Stretch`, `⚡ Sprint`, `🎯 Deep Work`) and reorder presets dynamically.
- **Chime Behaviors**: Single chime (3s), Continuous loop (click to dismiss), and Silent visual flash notifications.

### Comprehensive Context Menus
- **Lecture Table Row Actions**: Set reminder directly to lecture duration, start dedicated study session, reveal video file in Windows File Explorer, and copy titles/paths to clipboard.
- **Wall-Clock Alarm**: Set reminder countdown to target a specific wall-clock time (e.g. 05:30) with real-time countdown delta preview.

---

## Getting Started

### Option 1: Standalone Windows Executable (Recommended)
Download and run `dist/GitVLMPC.exe` directly — zero dependencies or Python installation required!

```powershell
.\dist\GitVLMPC.exe
```

### Option 2: Run with Python
```powershell
python -m pip install sounddevice numpy
python main.py
```

See [README.md](README.md) for full configuration details and player setup instructions.

---

## Requirements & Compatibility
- Windows 10 / 11 (64-bit).
- Compatible with MPC-BE (with Web Interface enabled) and VLC Media Player (with Lua HTTP interface enabled).
- Optional: macOS port available via `main_mac.py`.
