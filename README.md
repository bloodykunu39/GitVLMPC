# GitVLMPC - Lecture Progress Tracker (MPC-BE & VLC)

A desktop app that tracks lecture video progress, study sessions, ratings, and analytics in real time while using **MPC-BE** or **VLC Media Player**.

---

## Requirements

- **Operating System:** Windows
- **Python:** Python 3.9 or newer
- **Media Players:**
  - **MPC-BE** (with Web Interface enabled on port `13579`) and/or
  - **VLC Media Player** (with Lua HTTP Web interface enabled on port `8080`)
- **(Optional) FFmpeg:** Installed with `ffprobe.exe` in `PATH` for instant file scanning. If FFmpeg is not installed, video durations are automatically captured when playing in MPC-BE or VLC.
- **(Optional) Focus Sound Libraries:**
  - `sounddevice` and `numpy`: For pure sinusoidal binaural beats (e.g. `pip install sounddevice numpy`).
  - `pygame`: For custom MP3 audio playback (e.g. `pip install pygame`).
  - *Note: GitVLMPC core runs entirely with standard Python libraries. Audio packages are only needed if you wish to use binaural beats or MP3 reminder chimes.*

---

## Media Player Setup Guides

The app includes a built-in **Player Guide** button in the toolbar, but you can also configure your player beforehand:

### Option A: MPC-BE Setup
1. Open MPC-BE.
2. Press `O` on your keyboard (or go to **View** &rarr; **Options**).
3. In the left navigation, select **Player** &rarr; **Web Interface**.
4. Check **[✓] Listen on port** (Default is `13579`).
5. Check **[✓] Allow access from localhost only** (recommended for security).
6. Click **Apply**, then **OK**.

### Option B: VLC Media Player Setup
1. Open VLC Media Player.
2. Go to **Tools** &rarr; **Preferences** (or press `Ctrl + P`).
3. Under **Show settings** at the bottom-left corner, select **All** (to reveal advanced settings).
4. In the left tree, select **Interface** &rarr; **Main interfaces**.
5. In the right panel, check **[✓] Web** (activates VLC's HTTP interface).
6. In the left tree, expand **Main interfaces** and click on **Lua**.
7. Under **Lua HTTP**, find **Password** and enter a password (e.g. `vlc`).
8. Notice the **Lua HTTP port** (default is `8080`).
9. Click **Save** at the bottom-right.
10. **⭐ RESTART VLC COMPLETELY ⭐** (VLC's web server will not start until VLC is restarted).
11. In the tracker's **Player Settings**, enter the same password you set in VLC.

---

## Run

1. Run:

   ```powershell
   python main.py
   ```

2. **Auto-Open Last Folder**: When you first run GitVLMPC, select your lecture video folder. GitVLMPC saves this in your user profile (`%APPDATA%\GitVLMPC\config.json`) and **automatically reopens your last folder** every time you launch the app!
3. To switch to a different folder at any time, simply click **Change Folder** in the top bar.
4. On first launch, the app prompts you to choose your preferred player mode (**Auto-detect**, **MPC-BE only**, or **VLC only**), with your priority preference. You can change this anytime via **Player Settings**.

The app supports common video formats including MP4, MKV, AVI, WebM, MOV, M4V, TS, M2TS, FLV, WMV, MPG, and MPEG.

Progress is stored in `.lecture_progress.json` inside the selected video folder. That file is ignored by Git because it is specific to each user.
Ratings use a 1-5 scale in 0.5-star steps.

---

## Aesthetics & Themes

GitVLMPC comes with two crafted UI aesthetics designed for focus and readability:
- **🖤 AMOLED Dark (Default)**: Pure pitch-black (`#000000`) background for OLED monitors and night study, with deep charcoal cards (`#0a0a0d`), high-contrast text, glowing cyan digital stopwatch, and vibrant accents.
- **🌓 Minimalist Light**: Clean Apple/Notion-inspired aesthetic with subtle off-white canvas (`#f8fafc`), crisp slate typography, and pure white cards (`#ffffff`).

### Switching Themes:
1. Click the **Settings ▾** dropdown on the top toolbar:
   - Click **🎨 Theme Settings (Light / AMOLED)...** to open the theme picker with a live visual preview card.
   - Or click **🌓 Toggle Theme (Light ⇄ AMOLED)** to flip instantly between light and dark modes.
2. Your chosen theme is automatically saved to `%APPDATA%\GitVLMPC\config.json` and remembered across app sessions.

---

## Standalone Executable (.exe)

You can build or run a standalone Windows `.exe` that requires no Python installation:

```powershell
pyinstaller GitVLMPC.spec
```

The resulting single-file executable is created in `dist/GitVLMPC.exe`. It can be moved anywhere on your system or shared with friends. It remembers your last opened lecture folder and settings automatically in `%APPDATA%\GitVLMPC\config.json`.

---

## Features

### Dual Media Player Support & Smart Auto-Detect
- **Supports MPC-BE and VLC**: Use either player, or both interchangeably.
- **Smart Auto-Detect**: Automatically tracks whichever player is currently active.
- **Tie-Breaker Priority**: If both MPC-BE and VLC are running at the same time, the app follows the one actively playing a lecture from your folder, or honors your configured priority preference (**Prioritize MPC-BE** / **Prioritize VLC**).
- **First-Run Onboarding**: Prompts user for their media player preference on first setup.
- **Settings Menu**: Unified top bar dropdown for **Preferences** (Player Modes & Ports), **Theme Settings**, and quick theme toggling.
- **Interactive Player Guide**: Built-in tabbed guide with step-by-step instructions and connection test buttons.

### Study Stopwatch & Live Reminder System
- **Digital Study Stopwatch**: High-contrast stopwatch with Start, Pause, and End controls.
- **Compact Lecture Badge**: Intelligently truncates long lecture filenames to save space (e.g. `First...End.mp4`) while displaying the full lecture title in a smooth hover tooltip.
- **Live Reminder Countdown Badge**: Displays remaining time until next study reminder chime (`[ 00:44:32 ]`).
- **Hover Information Tooltip**: Hovering over the countdown displays a near-mouse tooltip showing master status, live remaining time, sound engine details, volume, and quick interaction tips:
  ```
  Single-click to add time • Double-click to edit timer
  Right-click for timer options
  ```
- **Right-Click Timer Context Menu**: Right-clicking the timer label provides complete timer management:
  - Quick Add Time panel
  - Direct Edit Timer scroller
  - Cascading Presets sub-menu (+45m, +15m, etc.)
  - Restart Countdown from start
  - Reset to default interval (45m)
  - Toggle Reminder On/Off
  - Sound Settings shortcut
  - Test Play / Pause controls
- **Inline Quick-Add Panel (Right-Side Placement)**:
  - Single-clicking the live countdown opens a sleek floating panel placed directly on the **right side** of the label (no `tk.Toplevel` popup windows).
  - Automatically closes when clicking anywhere outside.
- **5 Sub-Buttons Total (4 Presets + 1 Custom)**:
  - **4 Preset Buttons** (Default: `+00:45:00`, `+00:15:00`, `+00:30:00`, `+00:05:00`): Left-clicking immediately adds/subtracts time relative to the live running countdown.
  - **Preset Right-Click Context Menu**: Right-clicking any preset button opens an isolated menu:
    - **Edit**: Inline HH:MM:SS scroller to edit duration and sign.
    - **Change to Opposite Sign**: Flips `+` $\leftrightarrow$ `-` instantly.
    - **Remove**: Deletes that preset button.
    - **Add a Custom Box**: Adds/creates a custom preset.
  - **1 Custom Button (`✎ Custom`)**: Switches inline to custom mode with a `+ Add to Countdown` / `- Subtract from Countdown` toggle and full scroller controls.
- **Interactive Time Scroller (`HH : MM : SS`)**:
  - Independent segment boxes for **HH** (`00`–`99`, clamped), **MM** (`00`–`59`, wrap), and **SS** (`00`–`59`, wrap).
  - Mousewheel scrolling over any segment adjusts only that segment. Supports keyboard arrow keys and direct typing.
- **Double-Click Direct Edit**:
  - Double-clicking the countdown label directly opens an in-place HH:MM:SS editor to set the live countdown to any exact value.

### Focus Sound Engine (Binaural Beats & MP3)
- **Binaural Beat Generation**: Built-in tone generator creates pure sinusoidal waves with independent Left and Right channel frequencies (default: 200 Hz Left / 204 Hz Right for a 4 Hz theta focus beat) using `sounddevice` and `numpy`.
- **Custom MP3 Audio Playback**: Supports playing custom audio files as study chimes via `pygame`.
- **Collapsible Settings Panel (`⚙ Settings ▸`)**: Slides open inline below the stopwatch bar to configure sound modes, left/right frequencies, MP3 file browser, and master volume slider with live percentage feedback.
- **Test Play / Pause Buttons**: Dedicated `▶ Play` and `⏸ Pause` buttons to test and preview focus audio indefinitely without starting a study session.
- **Automatic Audio Cue**: Chimes automatically when the live countdown reaches zero during an active session, then resets for the next cycle.

### Progress & Analytics
- Detects lecture durations with FFmpeg's `ffprobe`.
- Reads playback position in real time from the active player.
- Tracks furthest position reached for each lecture.
- Shows total, covered, remaining, and overall progress in clickable metric chips.
- Double-clicks on Total, Covered, Remaining, Average rating, or Study time open interactive Pie and Bar charts styled to match your active theme.
- Double-clicking a lecture's Time Spent cell opens a session-wise chart with session time, video-playing time, and percentage share on hover.
- Rating bar chart plots lecture count against 1-5 ratings and marks the average rating with a line.

### Study Sessions & Activity History
- Timestamped sessions group multiple lectures and replay segments under IDs like `Session0001`.
- Compact session activity panel shows session total, actual video-playing total, and a scrollable segment breakdown.
- Filter activity by current session, historical session, or all sessions.
- Optional auto-start when a player begins playing a recognized lecture.

### Lecture Organization
- 1-5 star ratings with 0.5-star adjustments (via mouse wheel or spinner) and multiline reviews.
- Color coding for watched, in-progress, and unwatched lectures.
- Fast filename search and filtering.
- Bulk selection mode (select all, unselect all, mark watched/unwatched in bulk).
- Right-click actions to mark watched, set covered time, or set to current player position.
- Portable JSON export and import for progress, notes, and study sessions.
