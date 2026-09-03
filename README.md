# MPC-BE Lecture Progress

A small Windows desktop app that tracks lecture video progress while using MPC-BE.

## Requirements

- Windows
- Python 3.9 or newer
- MPC-BE with its web interface enabled on port `13579`
- FFmpeg installed and `ffprobe.exe` available in `PATH`

Python packages are not required. The app uses only the Python standard library.

## Run

1. Install Python and FFmpeg.
2. Enable MPC-BE's web interface. The default port expected by this app is `13579`.
3. Run:

   ```powershell
   python main.py
   ```

4. Choose the folder containing your lecture videos when prompted.

The app supports common video formats including MP4, MKV, AVI, WebM, MOV, M4V, TS, M2TS, FLV, WMV, MPG, and MPEG.

Progress is stored in `.lecture_progress.json` inside the selected video folder. That file is ignored by Git because it is specific to each user.
Checkbox selections are temporary and are cleared when selection mode is closed or the app is restarted.

## Features

- Detects lecture durations with FFmpeg's `ffprobe`.
- Reads the currently playing file and position from MPC-BE.
- Tracks the furthest position reached for each lecture.
- Shows total, covered, remaining, and overall progress.
- Sorts the lecture table by clicking any column heading; click again to reverse the order.
- Enables checkbox selection from a lecture's right-click menu and supports selecting all visible lectures.
- Provides right-click actions to mark lectures watched or unwatched, remove them from the tracker, or exit selection mode.
- In selection mode, applies watched status, covered time, and current MPC-BE position actions to all checked lectures.
- Allows lectures to be marked watched or unwatched manually.
- Allows lectures to be removed from the tracker without deleting the video file.
- Allows removed lectures to be restored with the `Restore Removed` button.
- Allows covered time to be entered manually.
- Can inspect common MPC-BE/MPC-HC recent-file registry locations.

## Limitations

This app is currently Windows-only because it uses Windows registry access and Windows file-opening APIs. It matches the currently playing video by filename, so duplicate filenames in different folders may be ambiguous.
