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

4. Choose the folder containing your lecture videos when prompted. You can change it later with **Change Folder**.

The app supports common video formats including MP4, MKV, AVI, WebM, MOV, M4V, TS, M2TS, FLV, WMV, MPG, and MPEG.

Progress is stored in `.lecture_progress.json` inside the selected video folder. That file is ignored by Git because it is specific to each user.
Checkbox selections are temporary and are cleared when selection mode is closed or the app is restarted.
Ratings use a 1-5 scale. The average rating excludes lectures without a rating, and ratings/reviews are included in progress exports.

## Features

- Detects lecture durations with FFmpeg's `ffprobe`.
- Reads the currently playing file and position from MPC-BE.
- Tracks the furthest position reached for each lecture.
- Shows total, covered, remaining, and overall progress.
- Stores a 1-5 rating and review for each lecture and shows the average rating.
- Provides a user-controlled study stopwatch for the selected lecture with Start, Pause, Resume, and Stop.
- Saves timestamped sessions, shows per-lecture Time Spent, total Study time, and a session history.
- Groups multiple lectures and replay segments under one dated ID such as `Session0001` until the user ends the session.
- Shows a compact activity area with session total, actual video-playing total, and a scrollable segment list.
- Shows a scrollable activity table with separate session time and actual video-playing time for every segment.
- Supports manually added segments and hiding/showing the activity panel without stopping tracking.
- Detects the current lecture directly from MPC-BE, so starting a session never requires selecting a table row.
- Counts session time only while the app session is active and MPC-BE reports playback; app controls never play, pause, stop, or seek MPC-BE.
- Can automatically start tracking when MPC-BE is already playing a recognized lecture, with an option to disable auto-start.
- Double-click a Rating cell to open the rating spinner; use its arrows or mouse wheel to adjust the value.
- Double-click a Review cell to edit the review in a multiline text box and save it.
- Colors identify watched, in-progress, and not-watched lecture rows.
- Searches lectures by filename.
- Refreshes the folder automatically every 10 seconds.
- Opens a lecture in the Windows default video player when double-clicking its Lecture cell.
- Exports and imports progress using portable JSON files.
- Exports and imports saved study sessions with progress data.
- Allows the MPC-BE web interface port to be changed and tested.
- Sorts the lecture table by clicking any column heading; click again to reverse the order.
- Enables checkbox selection from a lecture's right-click menu and supports selecting all visible lectures.
- Provides selection controls for selecting all, unselecting all, viewing the selected count, and exiting selection mode.
- Provides right-click actions to mark lectures watched or unwatched, set covered time, use the current MPC-BE position, or remove them from the tracker.
- In selection mode, applies watched status, covered time, and current MPC-BE position actions to all checked lectures.
- Allows lectures to be marked watched or unwatched manually.
- Allows lectures to be removed from the tracker without deleting the video file.
- Allows removed lectures to be restored with the `Restore Removed` button.
- Allows covered time to be entered manually.
- Can inspect common MPC-BE/MPC-HC recent-file registry locations.

## Limitations

This app is currently Windows-only because it uses Windows registry access and Windows file-opening APIs. It matches the currently playing video by filename, so duplicate filenames in different folders may be ambiguous.
