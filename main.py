import base64, json, math, os, re, shutil, socket, subprocess, threading, time, tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog, filedialog
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import unquote
import winreg

APP_NAME = "GitVLMPC"

def get_app_config_path():
    appdata = os.environ.get("APPDATA")
    if appdata:
        cfg_dir = Path(appdata) / APP_NAME
    else:
        cfg_dir = Path.home() / f".{APP_NAME.lower()}"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.json"

def load_last_folder():
    try:
        cfg_path = get_app_config_path()
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            folder = cfg.get("last_folder")
            if folder and Path(folder).is_dir():
                return Path(folder)
    except Exception:
        pass
    return None

def save_last_folder(folder_path):
    try:
        cfg_path = get_app_config_path()
        cfg = {}
        if cfg_path.exists():
            try: cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception: cfg = {}
        cfg["last_folder"] = str(folder_path)
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

THEMES = {
    "light": {
        "name": "Minimalist Light",
        "bg": "#f8fafc",
        "fg": "#0f172a",
        "card_bg": "#ffffff",
        "border": "#cbd5e1",
        "accent": "#4f46e5",
        "accent_text": "#ffffff",
        "muted": "#64748b",
        "tree_bg": "#ffffff",
        "tree_fg": "#0f172a",
        "tree_sel_bg": "#e0e7ff",
        "tree_sel_fg": "#3730a3",
        "tree_watched": "#dcfce7",
        "tree_progress": "#fef3c7",
        "tree_unwatched": "#fee2e2",
        "card_title_fg": "#1e293b",
        "stopwatch_bg": "#f1f5f9",
        "stopwatch_fg": "#0f172a",
        "chip_bg": "#ffffff",
        "chip_fg": "#334155",
        "chip_border": "#cbd5e1",
        "trough": "#e2e8f0"
    },
    "amoled": {
        "name": "AMOLED Dark",
        "bg": "#000000",
        "fg": "#f8fafc",
        "card_bg": "#0a0a0d",
        "border": "#272730",
        "accent": "#6366f1",
        "accent_text": "#ffffff",
        "muted": "#94a3b8",
        "tree_bg": "#050507",
        "tree_fg": "#f1f5f9",
        "tree_sel_bg": "#2e2e48",
        "tree_sel_fg": "#e0e7ff",
        "tree_watched": "#062817",
        "tree_progress": "#2b2105",
        "tree_unwatched": "#2d0a0f",
        "card_title_fg": "#818cf8",
        "stopwatch_bg": "#07070a",
        "stopwatch_fg": "#38bdf8",
        "chip_bg": "#0d0d12",
        "chip_fg": "#cbd5e1",
        "chip_border": "#272730",
        "trough": "#1e1e24"
    }
}

def load_app_theme():
    try:
        cfg_path = get_app_config_path()
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            theme = cfg.get("theme", "amoled")
            if theme in THEMES:
                return theme
    except Exception:
        pass
    return "amoled"

def save_app_theme(theme_key):
    try:
        cfg_path = get_app_config_path()
        cfg = {}
        if cfg_path.exists():
            try: cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception: cfg = {}
        cfg["theme"] = theme_key
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

VIDEO_DIR = None
DATA_FILE = None
DEFAULT_MPC_PORT = 13579
DEFAULT_VLC_PORT = 8080
DEFAULT_PLAYER_MODE = "auto"
DEFAULT_PRIORITY_PLAYER = "mpc"

MPC_PORT = DEFAULT_MPC_PORT
VLC_PORT = DEFAULT_VLC_PORT
VLC_PASSWORD = ""
PLAYER_MODE = DEFAULT_PLAYER_MODE
PRIORITY_PLAYER = DEFAULT_PRIORITY_PLAYER
EXTS = {".mp4",".mkv",".avi",".webm",".mov",".m4v",".ts",".m2ts",".flv",".wmv",".mpg",".mpeg"}

def fmt(s):
    s=max(0,int(s or 0)); h,r=divmod(s,3600); m,sec=divmod(r,60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
def big(s):
    s=max(0,int(s or 0)); h,r=divmod(s,3600); return f"{h}h {r//60:02d}m"

_vids_cache = None

def clear_vids_cache():
    global _vids_cache
    _vids_cache = None

def vids():
    global _vids_cache
    if _vids_cache is not None:
        return _vids_cache
    if not VIDEO_DIR or not VIDEO_DIR.exists():
        _vids_cache = []
        return []
    try:
        _vids_cache = sorted([p for p in VIDEO_DIR.iterdir() if p.is_file() and p.suffix.lower() in EXTS],
                             key=lambda x: x.name.lower())
    except Exception:
        _vids_cache = []
    return _vids_cache

def is_port_open(port, timeout=0.08):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except Exception:
        return False

def load():
    try: return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except: return {}
def save(d):
    DATA_FILE.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding="utf-8")

def duration_ffprobe(p):
    try:
        r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                          "-of","default=noprint_wrappers=1:nokey=1",str(p)],
                         capture_output=True,text=True,timeout=8)
        return float(r.stdout.strip()) if r.returncode==0 else 0
    except: return 0

def tag(html,id):
    m=re.search(rf'<[^>]*id=["\']{re.escape(id)}["\'][^>]*>(.*?)</',html,re.I|re.S)
    return re.sub("<[^>]+>","",m.group(1)).strip() if m else ""

def mpc(port=None):
    port = port or MPC_PORT
    if not is_port_open(port):
        return None
    try:
        with urlopen(f"http://127.0.0.1:{port}/variables.html",timeout=0.8) as r:
            h=r.read().decode("utf-8","replace")
        pos=float(tag(h,"position") or 0)/1000
        dur=float(tag(h,"duration") or 0)/1000
        state=tag(h,"statestring") or "Playing"
        return {"path":unquote(tag(h,"filepath")),
                "pos":pos,
                "dur":dur,
                "ps":tag(h,"positionstring") or fmt(pos),
                "ds":tag(h,"durationstring") or fmt(dur),
                "state":state,
                "player":"MPC-BE"}
    except: return None

def vlc(port=None, password=None):
    port = port or VLC_PORT
    if not is_port_open(port):
        return None
    password = password if password is not None else VLC_PASSWORD
    try:
        url = f"http://127.0.0.1:{port}/requests/status.json"
        auth_bytes = f":{password}".encode("utf-8")
        auth_header = "Basic " + base64.b64encode(auth_bytes).decode("ascii")
        req = Request(url, headers={"Authorization": auth_header, "User-Agent": "LectureProgressTracker"})
        with urlopen(req, timeout=0.8) as r:
            raw = json.loads(r.read().decode("utf-8", "replace"))
        meta = raw.get("information", {}).get("category", {}).get("meta", {})
        uri = meta.get("uri") or meta.get("url") or meta.get("filename") or ""
        if uri.startswith("file:///"):
            path = unquote(uri[8:])
            if len(path) > 2 and path[1] == ":":
                path = path.replace("/", "\\")
        else:
            path = unquote(uri)
        pos = float(raw.get("time") or 0)
        dur = float(raw.get("length") or 0)
        raw_state = str(raw.get("state") or "").lower()
        state = "Playing" if raw_state == "playing" else "Paused" if raw_state == "paused" else "Stopped"
        return {
            "path": path,
            "pos": pos,
            "dur": dur,
            "ps": fmt(pos),
            "ds": fmt(dur),
            "state": state,
            "player": "VLC"
        }
    except: return None

def poll_player():
    if PLAYER_MODE == "mpc": return mpc()
    if PLAYER_MODE == "vlc": return vlc()
    m_info = mpc()
    v_info = vlc()
    if m_info and not v_info: return m_info
    if v_info and not m_info: return v_info
    if not m_info and not v_info: return None
    m_play = str(m_info.get("state","")).lower() in {"playing","play","running"}
    v_play = str(v_info.get("state","")).lower() in {"playing","play","running"}
    if m_play and not v_play: return m_info
    if v_play and not m_play: return v_info
    def matches_lecture(info):
        p = info.get("path") or ""
        name = Path(p).name.lower()
        return any(v.name.lower() == name for v in vids())
    m_match = matches_lecture(m_info)
    v_match = matches_lecture(v_info)
    if m_match and not v_match: return m_info
    if v_match and not m_match: return v_info
    return m_info if PRIORITY_PLAYER == "mpc" else v_info

def test_mpc_conn(port=None):
    port = port or MPC_PORT
    try:
        with urlopen(f"http://127.0.0.1:{port}/variables.html", timeout=1.5) as r:
            h = r.read().decode("utf-8", "replace")
        info = mpc(port)
        playing_str = f"\nCurrently open: {Path(info['path']).name}" if (info and info.get("path")) else ""
        return True, f"Connected to MPC-BE on port {port}!{playing_str}"
    except Exception:
        return False, (
            f"Could not connect to MPC-BE on port {port}.\n\n"
            "Checklist:\n"
            "1. Is MPC-BE running?\n"
            f"2. In MPC-BE: Options (press O) → Player → Web Interface → check 'Listen on port' ({port}).\n"
            "3. Check 'Allow access from localhost only'.\n"
            "4. Click OK in MPC-BE options."
        )

def test_vlc_conn(port=None, password=None):
    port = port or VLC_PORT
    password = password if password is not None else VLC_PASSWORD
    try:
        url = f"http://127.0.0.1:{port}/requests/status.json"
        auth_bytes = f":{password}".encode("utf-8")
        auth_header = "Basic " + base64.b64encode(auth_bytes).decode("ascii")
        req = Request(url, headers={"Authorization": auth_header, "User-Agent": "LectureProgressTracker"})
        with urlopen(req, timeout=1.5) as r:
            raw = json.loads(r.read().decode("utf-8", "replace"))
        meta = raw.get("information", {}).get("category", {}).get("meta", {})
        title = meta.get("filename") or meta.get("title") or "No file currently loaded"
        state = raw.get("state", "unknown")
        return True, f"Connected to VLC on port {port}!\n\nStatus: {state}\nMedia: {title}"
    except HTTPError as e:
        if e.code == 401:
            return False, (
                f"VLC responded on port {port}, but Password Failed (401 Unauthorized).\n\n"
                "Please verify the password in Player Settings matches your VLC setting:\n"
                "In VLC: Tools → Preferences → Show settings: All → Interface → Main interfaces → Lua → Lua HTTP password."
            )
        return False, f"VLC HTTP Error: {e.code} {e.reason}"
    except Exception:
        return False, (
            f"Could not connect to VLC on port {port}.\n\n"
            "Checklist:\n"
            "1. Is VLC running?\n"
            "2. In VLC: Tools → Preferences → Show settings: All → Interface → Main interfaces → Check 'Web'.\n"
            "3. Under Interface → Main interfaces → Lua → Enter a Password under 'Lua HTTP'.\n"
            "4. IMPORTANT: Restart VLC after changing these settings!"
        )

def registry_history():
    """Best-effort import of MPC-HC/MPC-BE recent-file history.
    Exact stored position is not guaranteed by every build."""
    out=[]
    roots=[
        (winreg.HKEY_CURRENT_USER,r"Software\MPC-BE MPC-BE"),
        (winreg.HKEY_CURRENT_USER,r"Software\MPC-BE"),
        (winreg.HKEY_CURRENT_USER,r"Software\MPC-HC"),
        (winreg.HKEY_CURRENT_USER,r"Software\Gabest\Media Player Classic")
    ]
    def walk(root,key):
        try:
            k=winreg.OpenKey(root,key)
            i=0
            while True:
                try:
                    name,val,typ=winreg.EnumValue(k,i); i+=1
                    if isinstance(val,str) and Path(val).suffix.lower() in EXTS:
                        out.append(val)
                except OSError: break
            i=0
            while True:
                try:
                    sub=winreg.EnumKey(k,i); i+=1; walk(root,key+"\\"+sub)
                except OSError: break
            winreg.CloseKey(k)
        except: pass
    for r,k in roots: walk(r,k)
    return list(dict.fromkeys(out))

class FocusSoundEngine:
    """
    Plays a binaural-beat sine pair (sounddevice + numpy) or an MP3 (pygame).
    Gracefully degrades if dependencies are not installed.
    All public methods are safe to call from any thread.
    """
    _libs_checked = False
    _sd_ok = False   # sounddevice + numpy available
    _pg_ok = False   # pygame available

    @classmethod
    def _check_libs(cls):
        if cls._libs_checked:
            return
        cls._libs_checked = True
        try:
            import sounddevice as _sd  # noqa: F401
            import numpy as _np  # noqa: F401
            cls._sd_ok = True
        except ImportError:
            pass
        try:
            import pygame as _pg  # noqa: F401
            cls._pg_ok = True
        except ImportError:
            pass

    def __init__(self):
        self._mode = "sine"
        self._freq_l = 200.0
        self._freq_r = 204.0
        self._volume = 0.5
        self._mp3_path = ""
        self._stream = None        # sounddevice stream
        self._lock = threading.Lock()
        self._playing = False
        self._phase_l = 0.0
        self._phase_r = 0.0
        self._stop_after = None    # time.monotonic() deadline, or None
        self._pg_initialized = False

    def configure(self, mode, freq_l, freq_r, mp3_path, volume):
        was_playing = self._playing
        self.stop()
        with self._lock:
            self._mode = mode
            self._freq_l = float(freq_l)
            self._freq_r = float(freq_r)
            self._mp3_path = str(mp3_path)
            self._volume = max(0.0, min(1.0, float(volume)))
        if was_playing:
            self.play()

    def set_volume(self, v):
        self._volume = max(0.0, min(1.0, float(v)))
        if self._playing:
            if self._mode == "mp3" and self._pg_initialized:
                try:
                    import pygame
                    pygame.mixer.music.set_volume(self._volume)
                except Exception:
                    pass

    @property
    def is_playing(self):
        return self._playing

    def play(self, duration_s=None):
        """Start playback.  duration_s=None means play until stop() is called."""
        self._check_libs()
        with self._lock:
            if self._playing:
                return
            if self._mode == "sine":
                if not self._sd_ok:
                    return
                self._stop_after = time.monotonic() + duration_s if duration_s else None
                self._phase_l = 0.0
                self._phase_r = 0.0
                try:
                    import sounddevice as sd
                    self._stream = sd.OutputStream(
                        samplerate=44100,
                        channels=2,
                        dtype="float32",
                        blocksize=1024,
                        callback=self._sine_callback,
                        finished_callback=self._stream_finished,
                    )
                    self._stream.start()
                    self._playing = True
                except Exception:
                    self._stream = None
            else:
                # MP3 mode
                if not self._pg_ok or not self._mp3_path or not Path(self._mp3_path).is_file():
                    return
                try:
                    import pygame
                    if not self._pg_initialized:
                        pygame.mixer.init()
                        self._pg_initialized = True
                    pygame.mixer.music.load(self._mp3_path)
                    pygame.mixer.music.set_volume(self._volume)
                    loops = 0 if duration_s else -1
                    pygame.mixer.music.play(loops=loops)
                    self._playing = True
                    if duration_s:
                        # schedule stop via a daemon thread
                        t = threading.Timer(duration_s, self.stop)
                        t.daemon = True
                        t.start()
                except Exception:
                    pass

    def stop(self):
        with self._lock:
            if not self._playing and not self._stream:
                return
            self._playing = False
            stream_to_close = self._stream
            self._stream = None
            if self._pg_initialized:
                try:
                    import pygame
                    pygame.mixer.music.stop()
                except Exception:
                    pass

        # Close stream in a background thread so UI thread is never blocked
        if stream_to_close:
            def _async_close(s):
                try:
                    s.stop(ignore_errors=True)
                    s.close(ignore_errors=True)
                except Exception:
                    pass
            threading.Thread(target=_async_close, args=(stream_to_close,), daemon=True).start()

    def _sine_callback(self, outdata, frames, time_info, status):
        import numpy as np
        sr = 44100.0
        vol = self._volume
        # Check deadline or if playing has been stopped
        if not self._playing or (self._stop_after is not None and time.monotonic() >= self._stop_after):
            outdata[:] = 0
            import sounddevice as _sd_mod
            raise _sd_mod.CallbackStop()  # clean stop — no "Exception ignored" spam
        t_arr = (np.arange(frames) / sr).astype(np.float32)
        left = np.sin(2 * np.pi * self._freq_l * t_arr + self._phase_l).astype(np.float32) * vol
        right = np.sin(2 * np.pi * self._freq_r * t_arr + self._phase_r).astype(np.float32) * vol
        # update phase accumulators to avoid discontinuities
        self._phase_l = (self._phase_l + 2 * np.pi * self._freq_l * frames / sr) % (2 * np.pi)
        self._phase_r = (self._phase_r + 2 * np.pi * self._freq_r * frames / sr) % (2 * np.pi)
        outdata[:, 0] = left
        outdata[:, 1] = right

    def _stream_finished(self):
        with self._lock:
            self._playing = False
            self._stream = None

    @staticmethod
    def missing_libs_message(mode):
        if mode == "sine":
            return (
                "Focus Sound (Binaural Beat) requires additional libraries.\n\n"
                "Run this command in your terminal, then restart the app:\n\n"
                "    pip install sounddevice numpy\n"
            )
        return (
            "Focus Sound (MP3) requires pygame.\n\n"
            "Run this command in your terminal, then restart the app:\n\n"
            "    pip install pygame\n"
        )


class App:
    def __init__(self,root):
        self.root=root; self.root.title("GitVLMPC - Lecture Progress Tracker"); self.root.geometry("1120x720")
        self.folder_var=tk.StringVar(value=str(VIDEO_DIR))
        self.search_var=tk.StringVar()
        self.current_theme = load_app_theme()
        self.data=load(); self.load_settings(); self.session=None; self.active_segment=None; self.current_info=None; self.auto_block_path=None
        self._latest_player_info = None
        self._reminder_elapsed = 0
        self.sound_engine = FocusSoundEngine()
        self._poller_active = True
        self._poller_thread = threading.Thread(target=self._bg_poll_loop, daemon=True)
        self._poller_thread.start()
        self.build()
        self._apply_focus_sound_to_ui()
        self.apply_theme(self.current_theme)
        self.refresh()
        root.after(400,self.check_first_run)
        root.after(500,self.loop)
        root.after(10000,self.auto_refresh)
        root.protocol("WM_DELETE_WINDOW",self.close)

    def _bg_poll_loop(self):
        while getattr(self, "_poller_active", False):
            try:
                info = poll_player()
                self._latest_player_info = info
            except Exception:
                self._latest_player_info = None
            time.sleep(0.4)

    def apply_theme(self, theme_key):
        if theme_key not in THEMES:
            theme_key = "amoled"
        self.current_theme = theme_key
        t = THEMES[theme_key]

        self.root.configure(bg=t["bg"])
        self.main_canvas.configure(bg=t["bg"])

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Global element styles
        style.configure(".", background=t["bg"], foreground=t["fg"])
        style.configure("TFrame", background=t["bg"])
        style.configure("TLabel", background=t["bg"], foreground=t["fg"], font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=t["bg"], foreground=t["fg"], font=("Segoe UI", 18, "bold"))
        style.configure("Muted.TLabel", background=t["bg"], foreground=t["muted"], font=("Segoe UI", 9))

        # Cards & LabelFrames
        style.configure("TLabelframe", background=t["card_bg"], bordercolor=t["border"], relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=t["card_bg"], foreground=t["card_title_fg"], font=("Segoe UI", 10, "bold"))

        # Buttons
        style.configure("TButton", background=t["card_bg"], foreground=t["fg"], bordercolor=t["border"],
                        darkcolor=t["card_bg"], lightcolor=t["card_bg"], focuscolor=t["accent"],
                        padding=(10, 4), font=("Segoe UI", 9))
        style.map("TButton",
                  background=[("active", t["accent"]), ("pressed", t["accent"])],
                  foreground=[("active", t["accent_text"]), ("pressed", t["accent_text"])],
                  bordercolor=[("active", t["accent"])])

        # Menubutton
        style.configure("TMenubutton", background=t["card_bg"], foreground=t["fg"], bordercolor=t["border"],
                        padding=(10, 4), font=("Segoe UI", 9))
        style.map("TMenubutton",
                  background=[("active", t["accent"])],
                  foreground=[("active", t["accent_text"])])

        # Inputs
        style.configure("TEntry", fieldbackground=t["card_bg"], foreground=t["fg"], insertcolor=t["fg"],
                        bordercolor=t["border"], padding=4)
        style.configure("TCheckbutton", background=t["card_bg"], foreground=t["fg"], font=("Segoe UI", 9))
        style.configure("TRadiobutton", background=t["card_bg"], foreground=t["fg"], font=("Segoe UI", 9))

        # Progress bars
        style.configure("Horizontal.TProgressbar", troughcolor=t["trough"], background=t["accent"],
                        bordercolor=t["border"], lightcolor=t["accent"], darkcolor=t["accent"])

        # Treeviews
        style.configure("Treeview", background=t["tree_bg"], foreground=t["tree_fg"],
                        fieldbackground=t["tree_bg"], bordercolor=t["border"], rowheight=28,
                        font=("Segoe UI", 9))
        style.map("Treeview",
                  background=[("selected", t["tree_sel_bg"])],
                  foreground=[("selected", t["tree_sel_fg"])])
        style.configure("Treeview.Heading", background=t["card_bg"], foreground=t["fg"],
                        bordercolor=t["border"], relief="flat", font=("Segoe UI", 9, "bold"))
        style.map("Treeview.Heading",
                  background=[("active", t["border"])],
                  foreground=[("active", t["accent"])])

        style.configure("Vertical.TScrollbar", troughcolor=t["bg"], bordercolor=t["border"],
                        background=t["card_bg"], arrowcolor=t["fg"])

        # Tree tags
        self.tree.tag_configure("watched", background=t["tree_watched"], foreground=t["tree_fg"])
        self.tree.tag_configure("progress", background=t["tree_progress"], foreground=t["tree_fg"])
        self.tree.tag_configure("unwatched", background=t["tree_unwatched"], foreground=t["tree_fg"])

        # Explicit widget colors
        if hasattr(self, "header_title"):
            self.header_title.configure(foreground=t["fg"])
        if hasattr(self, "conn_label"):
            self.conn_label.configure(foreground=t["muted"])
        if hasattr(self, "folder_label"):
            self.folder_label.configure(foreground=t["muted"])
        if hasattr(self, "selected_count_label"):
            self.selected_count_label.configure(foreground=t["muted"])

        if hasattr(self, "summary_cards") and hasattr(self, "summary_labels"):
            for card, label in zip(self.summary_cards, self.summary_labels):
                card.configure(bg=t["chip_bg"], highlightbackground=t["chip_border"], highlightcolor=t["accent"])
                label.configure(bg=t["chip_bg"], fg=t["chip_fg"])

        if hasattr(self, "timer_badge") and hasattr(self, "timer_label"):
            self.timer_badge.configure(bg=t["stopwatch_bg"], highlightbackground=t["border"], highlightcolor=t["border"])
            self.timer_label.configure(bg=t["stopwatch_bg"], fg=t["stopwatch_fg"])

        if hasattr(self, "_update_sound_buttons"):
            self._update_sound_buttons()

        menu_opts = {
            "bg": t["card_bg"], "fg": t["fg"],
            "activebackground": t["accent"], "activeforeground": t["accent_text"],
            "selectcolor": t["accent"], "relief": "solid", "bd": 1
        }
        for m in (getattr(self, "menubar", None),
                  getattr(self, "file_menu", None),
                  getattr(self, "edit_menu", None),
                  getattr(self, "view_menu", None),
                  getattr(self, "charts_menu", None),
                  getattr(self, "player_menu", None),
                  getattr(self, "settings_menu", None),
                  getattr(self, "help_menu", None),
                  getattr(self, "other_session_menu", None)):
            if m:
                try: m.configure(**menu_opts)
                except Exception: pass

    def toggle_theme(self):
        new_theme = "light" if self.current_theme == "amoled" else "amoled"
        self.apply_theme(new_theme)
        save_app_theme(new_theme)

    def toggle_activity_panel(self):
        if self.activity_frame.winfo_ismapped():
            self.hide_activity()
        else:
            self.show_activity()

    def on_player_mode_menu(self):
        global PLAYER_MODE
        mode = self.player_mode_var.get()
        PLAYER_MODE = mode
        s = self.data.setdefault("_settings", {})
        s["player_mode"] = mode
        save(self.data)
        self.draw()

    def open_about(self):
        messagebox.showinfo(
            "About GitVLMPC",
            "GitVLMPC - Lecture Progress Tracker\n"
            "Version 2.1.0\n\n"
            "Real-time lecture tracking with dual MPC-BE & VLC support,\n"
            "study stopwatch, analytics charts, and AMOLED/Light aesthetics.\n\n"
            "Keyboard Shortcuts:\n"
            "• Ctrl+O: Change lecture folder\n"
            "• Ctrl+T: Toggle Theme (Light ⇄ AMOLED)\n"
            "• F5: Refresh videos & durations\n"
            "• Ctrl+A: Select all lectures\n"
            "• Esc: Unselect all\n"
            "• Ctrl+Q: Exit application\n"
            "• Double-click row: Open lecture video\n"
            "• Double-click metric chip: Open analytics chart\n"
            "• Right-click row: Fast actions menu"
        )

    def build(self):
        # Top-level Application Menu Bar (File, Edit, View, Player, Settings, Help)
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        # 1. File Menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label="📁 Change Folder...", accelerator="Ctrl+O", command=self.change_folder)
        self.file_menu.add_command(label="📂 Open in File Explorer", command=lambda: os.startfile(str(VIDEO_DIR)) if VIDEO_DIR else None)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="📤 Export Progress JSON...", command=self.export_progress)
        self.file_menu.add_command(label="📥 Import Progress JSON...", command=self.import_progress)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="❌ Exit", accelerator="Ctrl+Q", command=self.close)
        self.menubar.add_cascade(label="File", menu=self.file_menu)

        # 2. Edit Menu
        self.edit_menu = tk.Menu(self.menubar, tearoff=0)
        self.edit_menu.add_command(label="☑ Select All", accelerator="Ctrl+A", command=self.select_all)
        self.edit_menu.add_command(label="☐ Unselect All", accelerator="Esc", command=self.unselect_all)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="✓ Mark Selected as Watched", command=lambda: self.context_watched(self.selected(), True))
        self.edit_menu.add_command(label="○ Mark Selected as Not Watched", command=lambda: self.context_watched(self.selected(), False))
        self.edit_menu.add_command(label="⏱ Set Covered Time...", command=lambda: self.context_settime(self.selected()))
        self.edit_menu.add_command(label="📍 Set to Current Player Position", command=lambda: self.context_set_current(self.selected()))
        self.edit_menu.add_command(label="⭐ Edit Rating & Review...", command=lambda: self.context_rating_review(self.selected()))
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="🗑 Remove Selected", command=lambda: self.remove_selected() if self.select_mode else self.context_remove(self.selected()))
        self.edit_menu.add_command(label="♻ Restore Removed Lectures...", command=self.restore_removed)
        self.menubar.add_cascade(label="Edit", menu=self.edit_menu)

        # 3. View Menu
        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.view_menu.add_command(label="🔄 Refresh", accelerator="F5", command=self.refresh)
        self.view_menu.add_separator()
        self.view_menu.add_command(label="📋 Toggle Session Activity Panel", command=self.toggle_activity_panel)
        self.view_menu.add_command(label="🕒 Session History Window...", command=self.show_sessions)
        self.view_menu.add_separator()
        self.charts_menu = tk.Menu(self.view_menu, tearoff=0)
        self.charts_menu.add_command(label="📈 Overall Progress Chart", command=lambda: self.open_chart("overall"))
        self.charts_menu.add_command(label="⏱ Covered Time Chart", command=lambda: self.open_chart("covered"))
        self.charts_menu.add_command(label="⏳ Remaining Time Chart", command=lambda: self.open_chart("remaining"))
        self.charts_menu.add_command(label="⭐ Rating Distribution Chart", command=lambda: self.open_chart("rating"))
        self.charts_menu.add_command(label="🕒 Time Spent by Session Chart", command=lambda: self.open_chart("spent"))
        self.view_menu.add_cascade(label="📊 Analytics & Charts", menu=self.charts_menu)
        self.menubar.add_cascade(label="View", menu=self.view_menu)

        # 4. Player Menu
        self.player_menu = tk.Menu(self.menubar, tearoff=0)
        self.player_menu.add_command(label="🔌 Test Player Connection", command=self.test_player)
        self.player_menu.add_command(label="📜 Import MPC-BE History...", command=self.import_history)
        self.player_menu.add_separator()
        self.player_mode_var = tk.StringVar(value=PLAYER_MODE)
        self.player_menu.add_radiobutton(label="Auto-detect (MPC-BE & VLC)", variable=self.player_mode_var, value="auto", command=self.on_player_mode_menu)
        self.player_menu.add_radiobutton(label="MPC-BE Only", variable=self.player_mode_var, value="mpc", command=self.on_player_mode_menu)
        self.player_menu.add_radiobutton(label="VLC Only", variable=self.player_mode_var, value="vlc", command=self.on_player_mode_menu)
        self.player_menu.add_separator()
        self.player_menu.add_command(label="⚙ Player Preferences & Ports...", command=lambda: self.open_settings("pref"))
        self.menubar.add_cascade(label="Player", menu=self.player_menu)

        # 5. Settings Menu
        self.settings_menu = tk.Menu(self.menubar, tearoff=0)
        self.settings_menu.add_command(label="⚙ Preferences (Player Modes & Ports)...", command=lambda: self.open_settings("pref"))
        self.settings_menu.add_command(label="🎨 Theme Settings (Light / AMOLED)...", command=lambda: self.open_settings("theme"))
        self.settings_menu.add_separator()
        self.settings_menu.add_command(label="🌓 Toggle Theme (Light ⇄ AMOLED)", accelerator="Ctrl+T", command=self.toggle_theme)
        self.menubar.add_cascade(label="Settings", menu=self.settings_menu)

        # 6. Help Menu
        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.help_menu.add_command(label="📖 Player Setup Guide (MPC-BE & VLC)...", command=self.open_help_guide)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="ℹ About GitVLMPC...", command=self.open_about)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)

        # Bind keyboard shortcuts
        self.root.bind_all("<Control-o>", lambda e: self.change_folder())
        self.root.bind_all("<Control-O>", lambda e: self.change_folder())
        self.root.bind_all("<Control-t>", lambda e: self.toggle_theme())
        self.root.bind_all("<Control-T>", lambda e: self.toggle_theme())
        self.root.bind_all("<F5>", lambda e: self.refresh())
        self.root.bind_all("<Control-q>", lambda e: self.close())
        self.root.bind_all("<Control-Q>", lambda e: self.close())
        self.root.bind_all("<Control-a>", lambda e: self.select_all())
        self.root.bind_all("<Control-A>", lambda e: self.select_all())
        self.root.bind_all("<Escape>", lambda e: self.unselect_all())

        # Full-window vertical scrollbar & container canvas
        self.main_canvas = tk.Canvas(self.root, highlightthickness=0, yscrollincrement=1)
        self.window_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.window_scrollbar.set)
        
        self.window_scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)

        self.content = ttk.Frame(self.main_canvas)
        self.canvas_win = self.main_canvas.create_window((0, 0), window=self.content, anchor="nw")

        def _update_scrollregion(event=None):
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

        def _resize_content(event):
            self.main_canvas.itemconfig(self.canvas_win, width=event.width)

        self.content.bind("<Configure>", _update_scrollregion)
        self.main_canvas.bind("<Configure>", _resize_content)

        try:
            self.root.unbind_class("Treeview", "<MouseWheel>")
            self.root.unbind_class("Treeview", "<Shift-MouseWheel>")
        except Exception:
            pass

        def _on_mousewheel(event):
            if not event.delta:
                return
            scroll_speed = 24
            pixels = int(-1 * (event.delta / 120) * scroll_speed) if abs(event.delta) >= 120 else int(-1 * event.delta * (scroll_speed / 120))
            if pixels == 0:
                pixels = -scroll_speed if event.delta > 0 else scroll_speed
            direction = 1 if pixels > 0 else -1

            target = getattr(event, "widget", None)
            tree_widget = None
            w = target
            while w:
                if "treeview" in str(w).lower():
                    tree_widget = w
                    break
                w = getattr(w, "master", None)

            if not tree_widget:
                w = self.root.winfo_containing(event.x_root, event.y_root)
                while w:
                    if "treeview" in str(w).lower():
                        tree_widget = w
                        break
                    w = getattr(w, "master", None)

            if tree_widget:
                try:
                    first, last = tree_widget.yview()
                    can_scroll_down = (direction > 0 and last < 0.999)
                    can_scroll_up = (direction < 0 and first > 0.001)
                    if can_scroll_down or can_scroll_up:
                        self._tree_wheel_accum = getattr(self, "_tree_wheel_accum", 0) + event.delta
                        # Require 120 delta (1 notch = 1 row)
                        if abs(self._tree_wheel_accum) >= 120:
                            row_step = 1 if self._tree_wheel_accum < 0 else -1
                            self._tree_wheel_accum = 0
                            tree_widget.yview_scroll(row_step, "units")
                        return "break"
                    else:
                        self._tree_wheel_accum = 0
                except Exception:
                    pass

            self.main_canvas.yview_scroll(pixels, "units")
            return "break"

        self._on_mousewheel = _on_mousewheel
        self.root.bind_all("<MouseWheel>", _on_mousewheel)
        self.root.bind_all("<Button-4>", lambda e: self.main_canvas.yview_scroll(-24, "units"))
        self.root.bind_all("<Button-5>", lambda e: self.main_canvas.yview_scroll(24, "units"))

        f=ttk.Frame(self.content,padding=(14,12,14,6)); f.pack(fill="x")
        
        # Title and Player Connection Status
        header=ttk.Frame(f); header.pack(fill="x")
        self.header_title=ttk.Label(header,text="GitVLMPC - Lecture Progress Tracker",font=("Segoe UI",18,"bold"))
        self.header_title.pack(side="left")
        self.conn=tk.StringVar()
        self.conn_label=ttk.Label(header,textvariable=self.conn,font=("Segoe UI",10))
        self.conn_label.pack(side="right")
        self.folder_label=ttk.Label(f,textvariable=self.folder_var,font=("Segoe UI",9))
        self.folder_label.pack(anchor="w",pady=(1,6))

        # Top Action / Tab Bar with Settings Dropdown
        top_bar=ttk.Frame(f); top_bar.pack(fill="x",pady=(2,6))
        ttk.Button(top_bar,text="📁 Change Folder",command=self.change_folder).pack(side="left",padx=(0,6))
        ttk.Button(top_bar,text="🔄 Refresh",command=self.refresh).pack(side="left",padx=(0,6))
        ttk.Button(top_bar,text="🔌 Test Player",command=self.test_player).pack(side="left",padx=(0,6))
        ttk.Button(top_bar,text="📖 Setup Guide",command=self.open_help_guide).pack(side="left",padx=(0,6))
        ttk.Button(top_bar,text="📂 Open Folder",command=lambda:os.startfile(str(VIDEO_DIR)) if VIDEO_DIR else None).pack(side="left",padx=(0,6))
        ttk.Button(top_bar,text="♻ Restore Removed",command=self.restore_removed).pack(side="left",padx=(0,6))
        ttk.Button(top_bar,text="⚙ Settings ▾",command=lambda:self.open_settings("pref")).pack(side="left",padx=(0,6))

        # Search row
        search=ttk.Frame(f); search.pack(fill="x",pady=(4,8))
        ttk.Label(search,text="Search:").pack(side="left")
        ttk.Entry(search,textvariable=self.search_var,width=36).pack(side="left",padx=(6,8))
        ttk.Button(search,text="Change Folder",command=self.change_folder).pack(side="left")
        self.search_var.trace_add("write",lambda *_: self.draw())
        ttk.Button(search,text="Export Progress",command=self.export_progress).pack(side="right",padx=(6,0))
        ttk.Button(search,text="Import Progress",command=self.import_progress).pack(side="right")
        
        # Summary metric chips
        s=ttk.Frame(f); s.pack(fill="x",pady=10)
        self.vars=[tk.StringVar() for _ in range(6)]
        summary_names=("total","covered","remaining","overall","rating","study")
        self.summary_labels=[]
        self.summary_cards=[]
        for v,name in zip(self.vars,summary_names):
            card=tk.Frame(s,padx=12,pady=5,relief="solid",borderwidth=1,cursor="hand2")
            card.pack(side="left",padx=(0,8))
            label=tk.Label(card,textvariable=v,font=("Segoe UI",9,"bold"),cursor="hand2")
            label.pack()
            card.bind("<Double-Button-1>",lambda e,metric=name:self.open_chart(metric))
            label.bind("<Double-Button-1>",lambda e,metric=name:self.open_chart(metric))
            self.summary_labels.append(label)
            self.summary_cards.append(card)

        self.pb=ttk.Progressbar(f,maximum=100); self.pb.pack(fill="x")
        n=ttk.LabelFrame(self.content,text="Currently Playing",padding=10); n.pack(fill="x",padx=14,pady=10)
        self.now=tk.StringVar(value="Waiting for media player...")
        self.nd=tk.StringVar()
        self.npb=ttk.Progressbar(n,maximum=100); ttk.Label(n,textvariable=self.now,font=("Segoe UI",11,"bold")).pack(anchor="w")
        self.npb.pack(fill="x",pady=5); ttk.Label(n,textvariable=self.nd).pack(anchor="w")
        
        timer=ttk.LabelFrame(self.content,text="Study Stopwatch",padding=(10,6,10,6))
        timer.pack(fill="x",padx=14,pady=(0,6))

        # Row 1 — lecture name (truncated) + clock + session buttons
        row1 = ttk.Frame(timer); row1.pack(fill="x")
        self.timer_lecture_full = ""   # stores untruncated name for tooltip
        self.timer_lecture=tk.StringVar(value="Waiting for media player activity")
        self.timer_text=tk.StringVar(value="00:00:00")
        self._lec_label = ttk.Label(row1, textvariable=self.timer_lecture,
                                    font=("Segoe UI",10,"bold"), width=16, anchor="w")
        self._lec_label.pack(side="left")
        # tooltip on hover
        self._tooltip_id = None
        self._tooltip_win = None
        self._lec_label.bind("<Enter>",  self._tooltip_schedule)
        self._lec_label.bind("<Leave>",  self._tooltip_cancel)
        self._lec_label.bind("<Motion>", self._tooltip_schedule)

        self.timer_badge=tk.Frame(row1,padx=8,pady=2,relief="solid",borderwidth=1)
        self.timer_badge.pack(side="left",padx=(6,8))
        self.timer_label=tk.Label(self.timer_badge,textvariable=self.timer_text,font=("Consolas",13,"bold"))
        self.timer_label.pack()
        self.timer_badge.bind("<Button-3>", self._show_stopwatch_context_menu)
        self.timer_badge.bind("<Button-2>", self._show_stopwatch_context_menu)
        self.timer_label.bind("<Button-3>", self._show_stopwatch_context_menu)
        self.timer_label.bind("<Button-2>", self._show_stopwatch_context_menu)

        self.start_session_button=ttk.Button(row1,text="Start Session",command=self.start_session)
        self.start_session_button.pack(side="left")
        self.pause_session_button=ttk.Button(row1,text="Pause",command=self.pause_session,state="disabled")
        self.pause_session_button.pack(side="left",padx=4)
        self.stop_session_button=ttk.Button(row1,text="End",command=self.stop_session,state="disabled")
        self.stop_session_button.pack(side="left",padx=(0,6))
        self.auto_start=tk.BooleanVar(value=self.auto_start_value)
        self.auto_pause_on_video = tk.BooleanVar(value=getattr(self, "auto_pause_on_video_value", False))
        ttk.Checkbutton(row1,text="Auto-start",variable=self.auto_start,command=self.save_auto_start).pack(side="left",padx=4)
        ttk.Button(row1,text="History",command=self.show_sessions).pack(side="left",padx=4)

        # Row 2 — Focus Sound / Study Reminder (compact strip)
        row2_outer = ttk.Frame(timer); row2_outer.pack(fill="x", pady=(6, 0))
        sound_row = ttk.Frame(row2_outer); sound_row.pack(fill="x")

        # Master enable checkbox
        self.reminder_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(sound_row, text="🔔 Reminder:", variable=self.reminder_enabled,
                        command=self._on_reminder_toggle).pack(side="left")

        # Countdown label — single click → inline quick-add panel
        self._countdown_var = tk.StringVar(value="--:--:--")
        self.reminder_interval = tk.StringVar(value="2700")   # seconds
        self._reminder_interval_entry = tk.Label(
            sound_row, textvariable=self._countdown_var,
            font=("Consolas", 10, "bold"), fg="#38bdf8", bg="#07070a",
            relief="solid", bd=1, padx=6, cursor="hand2"
        )
        self._reminder_interval_entry.pack(side="left", padx=(4, 2))
        self._countdown_click_job = None
        self._reminder_interval_entry.bind("<Button-1>", self._on_countdown_click)
        self._reminder_interval_entry.bind("<Double-Button-1>", self._on_countdown_double_click)
        self._reminder_interval_entry.bind("<Button-3>", self._show_reminder_context_menu)
        self._reminder_interval_entry.bind("<Button-2>", self._show_reminder_context_menu)
        self._reminder_interval_entry.bind("<Enter>", self._reminder_tooltip_schedule)
        self._reminder_interval_entry.bind("<Motion>", self._reminder_tooltip_schedule)
        self._reminder_interval_entry.bind("<Leave>", self._reminder_tooltip_cancel)
        self._reminder_interval_entry.bind("<ButtonPress>", lambda e: self._reminder_tooltip_cancel())

        # ⚙ Settings toggle button
        self._settings_open = False
        self._settings_btn = ttk.Button(sound_row, text="⚙ Settings ▸",
                                        command=self._toggle_settings, width=12)
        self._settings_btn.pack(side="left", padx=(6, 4))

        ttk.Label(sound_row, text="|").pack(side="left", padx=4)

        # ▶ Play / ⏸ Pause test buttons
        self._test_playing = False
        self._play_btn = tk.Button(sound_row, text="▶ Play", command=self._toggle_test_sound,
                                   font=("Segoe UI", 9, "bold"), relief="solid", bd=1,
                                   padx=8, pady=2, cursor="hand2")
        self._play_btn.pack(side="left", padx=(0, 4))
        self._pause_btn = tk.Button(sound_row, text="⏸ Pause", command=self._pause_test,
                                    font=("Segoe UI", 9, "bold"), relief="solid", bd=1,
                                    padx=8, pady=2, cursor="hand2", state="disabled")
        self._pause_btn.pack(side="left")

        # ── Collapsible settings panel (hidden by default) ────────────────────
        self._settings_frame = ttk.LabelFrame(row2_outer, text="Sound Settings", padding=(8, 4))
        # (not packed — shown only when ⚙ Settings is clicked)

        # Sound mode radios
        mode_row = ttk.Frame(self._settings_frame); mode_row.pack(fill="x", pady=(0, 4))
        self.sound_mode = tk.StringVar(value="sine")
        ttk.Radiobutton(mode_row, text="Binaural Beat", variable=self.sound_mode,
                        value="sine", command=self._on_sound_mode_change).pack(side="left")
        ttk.Radiobutton(mode_row, text="MP3 File", variable=self.sound_mode,
                        value="mp3", command=self._on_sound_mode_change).pack(side="left", padx=(8, 0))

        # Freq L / R (sine mode) — inside settings panel
        self._freq_frame = ttk.Frame(mode_row)
        self._freq_frame.pack(side="left", padx=(12, 0))
        ttk.Label(self._freq_frame, text="L:").pack(side="left")
        self.freq_l = tk.StringVar(value="200")
        ttk.Entry(self._freq_frame, textvariable=self.freq_l, width=6).pack(side="left", padx=(2, 4))
        ttk.Label(self._freq_frame, text="R:").pack(side="left")
        self.freq_r = tk.StringVar(value="204")
        ttk.Entry(self._freq_frame, textvariable=self.freq_r, width=6).pack(side="left", padx=(2, 4))
        ttk.Label(self._freq_frame, text="Hz").pack(side="left")

        # MP3 path — inside settings panel
        self._mp3_frame = ttk.Frame(mode_row)
        self.mp3_path = tk.StringVar(value="")
        ttk.Entry(self._mp3_frame, textvariable=self.mp3_path, width=24).pack(side="left", padx=(12, 0))
        ttk.Button(self._mp3_frame, text="Browse", command=self._browse_mp3).pack(side="left", padx=(4, 0))

        # Volume slider — inside settings panel
        vol_row = ttk.Frame(self._settings_frame); vol_row.pack(fill="x")
        ttk.Label(vol_row, text="Volume:").pack(side="left")
        self.sound_vol = tk.DoubleVar(value=0.5)
        ttk.Scale(vol_row, variable=self.sound_vol, from_=0.0, to=1.0,
                  orient="horizontal", length=120,
                  command=lambda v: self.sound_engine.set_volume(float(v))).pack(side="left", padx=(6, 0))
        self._vol_pct_label = ttk.Label(vol_row, text="50%", width=4)
        self._vol_pct_label.pack(side="left", padx=4)
        def _update_vol_pct(v):
            self.sound_engine.set_volume(float(v))
            self._vol_pct_label.configure(text=f"{int(float(v)*100)}%")
        self.sound_vol.trace_add("write", lambda *_: _update_vol_pct(self.sound_vol.get()))

        # Quick-add panel state
        self._quick_panel = None
        self._quick_dismiss_id = None
        self._reminder_tip_id = None
        self._reminder_tip_win = None

        # Initial visibility
        self._on_sound_mode_change()
        self._on_reminder_toggle()


        self.activity_frame=ttk.LabelFrame(self.content,text="Session activity",padding=6)

        self.activity_frame.pack(fill="x",padx=14,pady=(0,10))
        activity_top=ttk.Frame(self.activity_frame); activity_top.pack(fill="x")
        self.session_total_text=tk.StringVar(value="Session total: 00:00")
        self.video_total_text=tk.StringVar(value="Video playing total: 00:00")
        ttk.Label(activity_top,textvariable=self.session_total_text).pack(side="left",padx=(0,18))
        ttk.Label(activity_top,textvariable=self.video_total_text).pack(side="left")
        self.activity_filter="all"
        ttk.Button(activity_top,text="Current Session",command=self.show_current_activity).pack(side="right")
        self.other_session_button=tk.Menubutton(activity_top,text="Other Session",relief="raised")
        self.other_session_menu=tk.Menu(self.other_session_button,tearoff=0)
        self.other_session_button.configure(menu=self.other_session_menu)
        self.other_session_menu.configure(postcommand=self.refresh_activity_menu)
        self.other_session_button.pack(side="right",padx=6)
        ttk.Button(activity_top,text="Show All",command=self.show_all_activity).pack(side="right",padx=6)
        ttk.Button(activity_top,text="Add manual segment",command=self.add_manual_segment).pack(side="right")
        self.hide_activity_button=ttk.Button(activity_top,text="Hide Activity",command=self.hide_activity)
        self.hide_activity_button.pack(side="right",padx=6)
        activity_body=ttk.Frame(self.activity_frame); activity_body.pack(fill="x",pady=(6,0))
        activity_cols=("session_name","lecture","started","session","video")
        self.activity_tree=ttk.Treeview(activity_body,columns=activity_cols,show="headings",height=4)
        self.activity_sort_column="started"; self.activity_sort_reverse=True
        for c,t,w in zip(activity_cols,("Session Name","Lecture","Start date + time","Session time","Video playing time"),(110,330,180,130,150)):
            self.activity_tree.heading(c,text=t,command=lambda column=c:self.sort_activity(column)); self.activity_tree.column(c,width=w,anchor="w" if c in ("lecture","started") else "center")
        activity_scroll=ttk.Scrollbar(activity_body,orient="vertical",command=self.activity_tree.yview)
        self.activity_tree.configure(yscrollcommand=activity_scroll.set); self.activity_tree.pack(side="left",fill="x",expand=True); activity_scroll.pack(side="right",fill="y")
        self.activity_tree.bind("<MouseWheel>", self._on_mousewheel)
        self.show_activity_button=ttk.Button(self.content,text="Show Activity",command=self.show_activity)
        self.body_frame=ttk.Frame(self.content,padding=(14,0,14,10)); self.body_frame.pack(fill="both",expand=True)
        cols=("select","lecture","status","covered","duration","progress","rating","review","spent"); self.tree=ttk.Treeview(self.body_frame,columns=cols,show="headings",height=16)
        self.sort_column="lecture"; self.sort_reverse=False
        self.select_mode=False; self.checked=set()
        for c,t,w in zip(cols,("Select","Lecture","Status","Covered","Duration","Progress","Rating","Review","Time Spent"),(0,390,120,105,105,85,70,250,100)):
            self.tree.heading(c,text=t,command=lambda column=c: self.sort_tree(column))
            self.tree.column(c,width=w,anchor="w" if c=="lecture" else "center",stretch=c!="select")
        self.tree.pack(side="left",fill="both",expand=True)
        sc=ttk.Scrollbar(self.body_frame,command=self.tree.yview); sc.pack(side="right",fill="y"); self.tree.configure(yscrollcommand=sc.set)
        self.tree.bind("<Button-3>",self.menu)
        self.tree.bind("<Button-1>",self.tree_click)
        self.tree.bind("<Double-1>",self.open_lecture)
        self.tree.bind("<MouseWheel>", self._on_mousewheel)
        # Bottom bar for multi-selection mode
        bottom_bar=ttk.Frame(self.content,padding=(14,4,14,8)); bottom_bar.pack(fill="x")
        self.select_all_button=ttk.Button(bottom_bar,text="Select all",command=self.select_all)
        self.unselect_all_button=ttk.Button(bottom_bar,text="Unselect all",command=self.unselect_all)
        self.done_selecting_button=ttk.Button(bottom_bar,text="Done",command=self.exit_select_mode)
        self.selected_count=tk.StringVar(value="")
        self.selected_count_label=ttk.Label(bottom_bar,textvariable=self.selected_count,foreground="#666")

    def refresh(self):
        clear_vids_cache()
        for p in vids():
            k=str(p.resolve()); r=self.data.setdefault(k,{"name":p.name,"duration":0,"furthest":0,"manual":False,"rating":0,"review":""})
            r.setdefault("rating",0); r.setdefault("review","")
            if not r.get("duration"):
                d=duration_ffprobe(p)
                if d:r["duration"]=d
        save(self.data); self.draw()

    def visible_vids(self):
        query=self.search_var.get().strip().lower()
        return [p for p in vids() if not query or query in p.name.lower()]

    def auto_refresh(self):
        clear_vids_cache()
        self.refresh()
        self.root.after(10000,self.auto_refresh)

    def change_folder(self):
        global VIDEO_DIR, DATA_FILE
        selected=filedialog.askdirectory(parent=self.root,initialdir=str(VIDEO_DIR) if VIDEO_DIR else None,title="Choose your lecture video folder")
        if not selected:return
        self.stop_session(save_session=True)
        self.exit_select_mode()
        clear_vids_cache()
        VIDEO_DIR=Path(selected); DATA_FILE=VIDEO_DIR / ".lecture_progress.json"
        save_last_folder(str(VIDEO_DIR))
        self.folder_var.set(str(VIDEO_DIR)); self.data=load(); self.load_settings(); self.refresh()

    def load_settings(self):
        global MPC_PORT, VLC_PORT, VLC_PASSWORD, PLAYER_MODE, PRIORITY_PLAYER
        settings = self.data.get("_settings", {})
        try:
            port = int(settings.get("mpc_port", DEFAULT_MPC_PORT))
            if 1 <= port <= 65535: MPC_PORT = port
        except (TypeError, ValueError): pass
        try:
            port = int(settings.get("vlc_port", DEFAULT_VLC_PORT))
            if 1 <= port <= 65535: VLC_PORT = port
        except (TypeError, ValueError): pass
        VLC_PASSWORD = str(settings.get("vlc_password", ""))
        PLAYER_MODE = str(settings.get("player_mode", DEFAULT_PLAYER_MODE)).lower()
        if PLAYER_MODE not in {"auto", "mpc", "vlc"}: PLAYER_MODE = DEFAULT_PLAYER_MODE
        PRIORITY_PLAYER = str(settings.get("priority_player", DEFAULT_PRIORITY_PLAYER)).lower()
        if PRIORITY_PLAYER not in {"mpc", "vlc"}: PRIORITY_PLAYER = DEFAULT_PRIORITY_PLAYER
        self.auto_start_value = bool(settings.get("auto_start", True))
        self.auto_pause_on_video_value = bool(settings.get("auto_pause_on_video", False))
        self.load_focus_sound_settings()

    def save_player_settings(self, mode, priority, mpc_p, vlc_p, vlc_pass):
        global MPC_PORT, VLC_PORT, VLC_PASSWORD, PLAYER_MODE, PRIORITY_PLAYER
        MPC_PORT = mpc_p
        VLC_PORT = vlc_p
        VLC_PASSWORD = vlc_pass
        PLAYER_MODE = mode
        PRIORITY_PLAYER = priority
        s = self.data.setdefault("_settings", {})
        s["player_mode"] = mode
        s["priority_player"] = priority
        s["mpc_port"] = mpc_p
        s["vlc_port"] = vlc_p
        s["vlc_password"] = vlc_pass
        save(self.data)
        self.draw()

    # ── Focus Sound helpers ──────────────────────────────────────────────────

    # ---- lecture name helpers -----------------------------------------------

    @staticmethod
    def _truncate_lecture(name, prefix=5, suffix=3):
        if not name or len(name) <= prefix + suffix + 3:
            return name
        return name[:prefix] + "..." + name[-suffix:]

    def _tooltip_schedule(self, event):
        self._tooltip_cancel(event)
        if self.timer_lecture_full:
            self._tooltip_id = self._lec_label.after(
                700, lambda: self._tooltip_show(event.x_root, event.y_root)
            )

    def _tooltip_cancel(self, event=None):
        if self._tooltip_id:
            self._lec_label.after_cancel(self._tooltip_id)
            self._tooltip_id = None
        if self._tooltip_win:
            try: self._tooltip_win.destroy()
            except Exception: pass
            self._tooltip_win = None

    def _tooltip_show(self, x, y):
        if not self.timer_lecture_full:
            return
        try:
            tw = tk.Toplevel(self.root)
            tw.overrideredirect(True)
            tw.attributes("-topmost", True)
            tw.geometry(f"+{x+12}+{y+8}")
            tk.Label(tw, text=self.timer_lecture_full,
                     font=("Segoe UI", 9), padx=8, pady=4,
                     bg="#1e293b", fg="#f1f5f9",
                     relief="solid", bd=1).pack()
            self._tooltip_win = tw
        except Exception:
            pass

    # ---- countdown helpers --------------------------------------------------

    def load_focus_sound_settings(self):
        """Load persisted focus-sound prefs; safe to call before build()."""
        fs = self.data.get("_settings", {}).get("focus_sound", {})
        # interval_sec (new) takes priority; fall back to interval_min (legacy)
        raw = fs.get("interval_sec", fs.get("interval_min", 45) * 60)
        self._fs_pending = {
            "enabled":      bool(fs.get("enabled", False)),
            "interval_sec": int(raw),
            "mode":         str(fs.get("mode", "sine")),
            "freq_l":       str(fs.get("freq_l", 200)),
            "freq_r":       str(fs.get("freq_r", 204)),
            "volume":       float(fs.get("volume", 0.5)),
            "mp3_path":     str(fs.get("mp3_path", "")),
        }
        # 4 timer presets: list of {"sign": "+" or "-", "seconds": int}
        default_presets = [
            {"sign": "+", "seconds": 2700},  # +00:45:00
            {"sign": "+", "seconds": 900},   # +00:15:00
            {"sign": "+", "seconds": 1800},  # +00:30:00
            {"sign": "+", "seconds": 300},   # +00:05:00
        ]
        raw_presets = fs.get("presets")
        if isinstance(raw_presets, list) and len(raw_presets) > 0:
            presets = []
            for p in raw_presets[:4]:
                if isinstance(p, dict) and "seconds" in p:
                    sign = "-" if str(p.get("sign", "+")).strip() in {"-", "−"} else "+"
                    tag = p.get("tag")
                    try:
                        sec = max(1, int(p.get("seconds", 900)))
                        item = {"sign": sign, "seconds": sec}
                        if tag:
                            item["tag"] = str(tag)
                        presets.append(item)
                    except (ValueError, TypeError):
                        pass
            self._timer_presets = presets if presets else list(default_presets)
        else:
            self._timer_presets = list(default_presets)

    def _apply_focus_sound_to_ui(self):
        """Push _fs_pending values into the tkinter variables (call after build)."""
        p = getattr(self, "_fs_pending", None)
        if not p:
            return
        self.reminder_enabled.set(p["enabled"])
        self.reminder_interval.set(str(p["interval_sec"]))
        self.sound_mode.set(p["mode"])
        self.freq_l.set(p["freq_l"])
        self.freq_r.set(p["freq_r"])
        self.sound_vol.set(p["volume"])
        self.mp3_path.set(p["mp3_path"])
        self.sound_engine.configure(p["mode"], p["freq_l"], p["freq_r"],
                                    p["mp3_path"], p["volume"])
        self._on_sound_mode_change()
        self._on_reminder_toggle()

    def save_focus_sound_settings(self):
        """Persist current focus-sound settings to the data JSON."""
        try:
            interval_sec = int(self.reminder_interval.get())
        except ValueError:
            interval_sec = 2700
        fs = {
            "enabled":      self.reminder_enabled.get(),
            "interval_sec": interval_sec,
            "mode":         self.sound_mode.get(),
            "freq_l":       self._safe_freq(self.freq_l.get(), 200),
            "freq_r":       self._safe_freq(self.freq_r.get(), 204),
            "volume":       round(self.sound_vol.get(), 3),
            "mp3_path":     self.mp3_path.get(),
            "presets":      getattr(self, "_timer_presets", []),
        }
        self.data.setdefault("_settings", {})["focus_sound"] = fs
        save(self.data)
        self.sound_engine.configure(fs["mode"], fs["freq_l"], fs["freq_r"],
                                    fs["mp3_path"], fs["volume"])

    @staticmethod
    def _safe_freq(val, default):
        try:
            f = float(val)
            return f if 20 <= f <= 20000 else default
        except (ValueError, TypeError):
            return default

    # ── Hover Tooltip & Context Menu for Reminder Time ───────────────────────

    def _reminder_tooltip_schedule(self, event):
        """Schedule showing the reminder info tooltip near mouse cursor."""
        self._reminder_tooltip_cancel()
        if getattr(self, "_quick_panel", None):
            return
        x, y = event.x_root, event.y_root
        self._reminder_tip_id = self._reminder_interval_entry.after(
            350, lambda: self._reminder_tooltip_show(x, y)
        )

    def _reminder_tooltip_cancel(self, event=None):
        """Cancel pending tooltip or destroy visible tooltip."""
        if getattr(self, "_reminder_tip_id", None):
            try:
                self._reminder_interval_entry.after_cancel(self._reminder_tip_id)
            except Exception:
                pass
            self._reminder_tip_id = None
        if getattr(self, "_reminder_tip_win", None):
            try:
                self._reminder_tip_win.destroy()
            except Exception:
                pass
            self._reminder_tip_win = None

    def _reminder_tooltip_show(self, x, y):
        """Display an informational tooltip near the cursor for Reminder Time."""
        if getattr(self, "_quick_panel", None):
            return
        try:
            tw = tk.Toplevel(self.root)
            tw.overrideredirect(True)
            tw.attributes("-topmost", True)
            tw.geometry(f"+{x + 12}+{y + 12}")

            frame = tk.Frame(tw, bg="#0d1117", relief="solid", bd=1,
                             highlightbackground="#38bdf8", highlightthickness=1,
                             padx=8, pady=6)
            frame.pack()

            # Status
            is_enabled = self.reminder_enabled.get()
            status_text = "Enabled" if is_enabled else "Disabled"
            status_color = "#3fb950" if is_enabled else "#8b949e"

            cur_live = self._get_current_live_seconds()
            rh, rr = divmod(cur_live, 3600); rm, rs = divmod(rr, 60)
            live_str = f"{rh:02d}:{rm:02d}:{rs:02d}"

            # Sound info
            mode = self.sound_mode.get()
            if mode == "sine":
                sound_info = f"Binaural Beat ({self.freq_l.get()}/{self.freq_r.get()} Hz)"
            else:
                p = self.mp3_path.get()
                sound_info = f"MP3 ({Path(p).name})" if p else "MP3 (None selected)"
            vol_pct = int(self.sound_vol.get() * 100)

            # Top row: Reminder Time + status badge
            top_row = tk.Frame(frame, bg="#0d1117")
            top_row.pack(fill="x", pady=(0, 2))
            tk.Label(top_row, text="🔔 Reminder Time", font=("Segoe UI", 9, "bold"),
                     bg="#0d1117", fg="#f0f6fc").pack(side="left")
            tk.Label(top_row, text=f"● {status_text}", font=("Segoe UI", 8, "bold"),
                     bg="#0d1117", fg=status_color).pack(side="right", padx=(8, 0))

            # Countdown info
            in_session = bool(self.session and self.session.get("status") == "active")
            lbl_mode = "Live Countdown:" if in_session else "Configured Interval:"
            time_row = tk.Frame(frame, bg="#0d1117")
            time_row.pack(anchor="w", pady=(1, 2))
            tk.Label(time_row, text=lbl_mode, font=("Segoe UI", 8),
                     bg="#0d1117", fg="#94a3b8").pack(side="left", padx=(0, 4))
            tk.Label(time_row, text=live_str, font=("Consolas", 10, "bold"),
                     bg="#0d1117", fg="#38bdf8").pack(side="left")

            # Sound line
            tk.Label(frame, text=f"Audio: {sound_info}  •  Vol: {vol_pct}%",
                     font=("Segoe UI", 8), bg="#0d1117", fg="#8b949e").pack(anchor="w", pady=(0, 4))

            # Separator
            tk.Frame(frame, bg="#30363d", height=1).pack(fill="x", pady=(1, 4))

            # Mandatory instructions specified by user:
            tk.Label(frame, text="Single-click to add time • Double-click to edit timer",
                     font=("Segoe UI", 8, "bold"), bg="#0d1117", fg="#58a6ff").pack(anchor="w")
            tk.Label(frame, text="Right-click for timer options",
                     font=("Segoe UI", 7), bg="#0d1117", fg="#6e7681").pack(anchor="w")

            self._reminder_tip_win = tw
        except Exception:
            pass

    def _show_reminder_context_menu(self, event):
        """Right-click on reminder time: context menu for managing timer actions."""
        self._reminder_tooltip_cancel()
        if self._quick_panel:
            self._close_quick_panel()

        menu = tk.Menu(self.root, tearoff=0, bg="#161b22", fg="#e6edf3",
                       activebackground="#1f6feb", activeforeground="#ffffff",
                       relief="solid", bd=1)

        menu.add_command(label="➕ Quick Add Time...", command=self._open_quick_add_panel)
        menu.add_command(label="✏️ Direct Edit Timer...", command=self._open_direct_edit_panel)
        menu.add_command(label="⏰ Remind at Clock Time...", command=self._open_wall_clock_panel)

        # Match Video Remaining Time
        info = getattr(self, "current_info", None) or poll_player()
        if info and info.get("dur", 0) > 0:
            rem_vid = max(0, int(info["dur"] - info.get("pos", 0)))
            rh, rr = divmod(rem_vid, 3600); rm, rs = divmod(rr, 60)
            vid_label = f"🎬 Match Video Remaining ({rh:02d}:{rm:02d}:{rs:02d})"
            menu.add_command(label=vid_label, command=lambda s=rem_vid: self._set_live_countdown_direct(s))
        else:
            menu.add_command(label="🎬 Match Video Remaining (No active video)", state="disabled")

        menu.add_separator()

        # Binaural Focus Modes submenu
        binaural_menu = tk.Menu(menu, tearoff=0, bg="#161b22", fg="#e6edf3",
                                activebackground="#1f6feb", activeforeground="#ffffff")
        binaural_presets = [
            ("Theta (4 Hz) — Deep Focus (200 / 204 Hz)", 200, 204),
            ("Alpha (10 Hz) — Flow State (200 / 210 Hz)", 200, 210),
            ("Beta (18 Hz) — Active Problem Solving (200 / 218 Hz)", 200, 218),
            ("Delta (2 Hz) — Deep Relaxation (200 / 202 Hz)", 200, 202),
            ("Gamma (40 Hz) — Peak Cognition (200 / 240 Hz)", 200, 240),
        ]
        cur_l = str(self.freq_l.get()).strip()
        cur_r = str(self.freq_r.get()).strip()
        is_sine = self.sound_mode.get() == "sine"
        for label, fl, fr in binaural_presets:
            prefix = "✓ " if (is_sine and cur_l == str(fl) and cur_r == str(fr)) else "   "
            binaural_menu.add_command(
                label=prefix + label,
                command=lambda l=fl, r=fr: self._set_binaural_preset(l, r)
            )
        menu.add_cascade(label="🧠 Binaural Focus Modes", menu=binaural_menu)

        # Standard Study Intervals submenu
        standards_menu = tk.Menu(menu, tearoff=0, bg="#161b22", fg="#e6edf3",
                                 activebackground="#1f6feb", activeforeground="#ffffff")
        intervals = [
            ("🍅 Pomodoro (25 min)", 1500),
            ("⏱ Standard (45 min)", 2700),
            ("🎯 Deep Work (60 min)", 3600),
            ("⚡ Ultradian Sprint (90 min)", 5400),
            ("☕ Quick Break (5 min)", 300),
            ("🚶 Long Break (15 min)", 900),
        ]
        for label, s in intervals:
            standards_menu.add_command(
                label=label,
                command=lambda sec=s: self._set_live_countdown_direct(sec)
            )
        menu.add_cascade(label="📅 Standard Study Intervals", menu=standards_menu)

        # Quick Volume Submenu
        vol_menu = tk.Menu(menu, tearoff=0, bg="#161b22", fg="#e6edf3",
                           activebackground="#1f6feb", activeforeground="#ffffff")
        cur_vol_pct = int(round(self.sound_vol.get() * 100))
        for pct in (100, 80, 60, 40, 20, 0):
            lbl_vol = f"{pct}%" if pct > 0 else "0% (Mute)"
            prefix = "✓ " if abs(cur_vol_pct - pct) <= 5 else "   "
            vol_menu.add_command(
                label=prefix + lbl_vol,
                command=lambda v=pct/100.0: self._quick_set_volume(v)
            )
        menu.add_cascade(label="🔊 Volume Level", menu=vol_menu)

        # Chime Behavior Mode
        chime_menu = tk.Menu(menu, tearoff=0, bg="#161b22", fg="#e6edf3",
                             activebackground="#1f6feb", activeforeground="#ffffff")
        chime_modes = [
            ("🔔 Single Chime (3 sec)", "once"),
            ("🔁 Continuous (until stopped)", "loop"),
            ("🔕 Silent Visual Flash Only", "silent"),
        ]
        cur_chime = self.data.get("_settings", {}).get("focus_sound", {}).get("chime_mode", "once")
        for label, mode_key in chime_modes:
            prefix = "✓ " if cur_chime == mode_key else "   "
            chime_menu.add_command(
                label=prefix + label,
                command=lambda m=mode_key: self._set_chime_mode(m)
            )
        menu.add_cascade(label="🔔 Chime Behavior", menu=chime_menu)

        menu.add_separator()

        # Preset sub-menu or direct deltas
        presets_menu = tk.Menu(menu, tearoff=0, bg="#161b22", fg="#e6edf3",
                               activebackground="#1f6feb", activeforeground="#ffffff")
        for p in getattr(self, "_timer_presets", []):
            lbl_p = self._format_preset_label(p)
            d = p["seconds"] if p.get("sign", "+") != "-" else -p["seconds"]
            presets_menu.add_command(label=f"Add {lbl_p}",
                                     command=lambda delta=d: self._apply_live_countdown_delta(delta))
        menu.add_cascade(label="Presets", menu=presets_menu)

        menu.add_command(label="🔄 Restart Countdown from Start", command=self._reset_live_countdown)
        menu.add_command(label="⏱ Reset Interval to Default (45m)", command=lambda: self._set_live_countdown_direct(2700))
        menu.add_separator()

        is_on = self.reminder_enabled.get()
        menu.add_command(
            label="🔔 Turn Reminder Off" if is_on else "🔔 Turn Reminder On",
            command=self._toggle_reminder_enabled
        )
        menu.add_command(label="⚙ Sound Settings...", command=self._toggle_settings)

        if getattr(self, "_test_playing", False):
            menu.add_command(label="⏸ Pause Test Sound", command=self._pause_test)
        else:
            menu.add_command(label="▶ Play Test Sound", command=self._play_test)

        menu.tk_popup(event.x_root, event.y_root)

    def _set_binaural_preset(self, fl, fr):
        """Set Left/Right binaural beat frequencies and activate sine mode."""
        self.sound_mode.set("sine")
        self.freq_l.set(str(fl))
        self.freq_r.set(str(fr))
        self._on_sound_mode_change()
        self.save_focus_sound_settings()

    def _quick_set_volume(self, v):
        """Quickly adjust focus sound volume from context menu."""
        self.sound_vol.set(v)
        self.sound_engine.set_volume(v)
        self.save_focus_sound_settings()

    def _set_chime_mode(self, mode_key):
        """Configure chime behavior: once, loop, or silent."""
        fs = self.data.setdefault("_settings", {}).setdefault("focus_sound", {})
        fs["chime_mode"] = mode_key
        save(self.data)

    def _open_wall_clock_panel(self):
        """Open inline panel on right side to set a reminder at a specific wall-clock time."""
        self._countdown_click_job = None
        if self._quick_panel:
            self._close_quick_panel()

        x, y = self._get_panel_xy()
        panel = tk.Frame(self.root, relief="solid", bd=1, bg="#0d1117",
                         highlightbackground="#30363d", highlightthickness=1,
                         padx=8, pady=8)
        panel.place(x=x, y=y)
        self._quick_panel = panel
        self._setup_outside_dismiss(panel)

        header = tk.Label(panel, text="Remind at Clock Time",
                          font=("Segoe UI", 9, "bold"), bg="#0d1117", fg="#38bdf8")
        header.pack(anchor="w", pady=(0, 4))

        now = datetime.now()
        target_default = now + timedelta(minutes=45)
        h_var = tk.StringVar(value=f"{target_default.hour:02d}")
        m_var = tk.StringVar(value=f"{target_default.minute:02d}")

        countdown_preview = tk.Label(panel, text="Countdown: +45m 00s",
                                     font=("Segoe UI", 8), bg="#0d1117", fg="#58a6ff")

        def _calc_delta():
            try:
                th = int(h_var.get()) % 24
                tm = int(m_var.get()) % 60
            except Exception:
                th, tm = now.hour, now.minute
            cur_now = datetime.now()
            target_dt = cur_now.replace(hour=th, minute=tm, second=0, microsecond=0)
            if target_dt <= cur_now:
                target_dt += timedelta(days=1)
            diff_s = max(1, int((target_dt - cur_now).total_seconds()))
            dh, drem = divmod(diff_s, 3600)
            dm, ds = divmod(drem, 60)
            countdown_preview.configure(text=f"Countdown: +{dh:02d}h {dm:02d}m {ds:02d}s")
            return diff_s

        def _step_h(delta):
            try: cur = int(h_var.get())
            except Exception: cur = 0
            new_v = (cur + delta) % 24
            h_var.set(f"{new_v:02d}")
            _calc_delta()

        def _step_m(delta):
            try: cur = int(m_var.get())
            except Exception: cur = 0
            new_v = (cur + delta) % 60
            m_var.set(f"{new_v:02d}")
            _calc_delta()

        digits_row = tk.Frame(panel, bg="#0d1117")
        digits_row.pack(pady=4)

        # HH Box (0-23)
        hh_box = tk.Entry(digits_row, textvariable=h_var, width=3,
                          font=("Consolas", 12, "bold"), justify="center",
                          bg="#161b22", fg="#38bdf8", insertbackground="#38bdf8",
                          relief="solid", bd=1)
        hh_box.pack(side="left", padx=2)
        hh_box.bind("<MouseWheel>", lambda e: (_step_h(1 if getattr(e, "delta", 0) > 0 else -1), "break")[1])
        hh_box.bind("<Up>", lambda e: (_step_h(1), "break")[1])
        hh_box.bind("<Down>", lambda e: (_step_h(-1), "break")[1])
        hh_box.bind("<Enter>", lambda e: hh_box.focus_set())
        hh_box.bind("<FocusOut>", lambda e: _calc_delta())

        tk.Label(digits_row, text=":", font=("Consolas", 12, "bold"),
                 bg="#0d1117", fg="#94a3b8").pack(side="left")

        # MM Box (0-59)
        mm_box = tk.Entry(digits_row, textvariable=m_var, width=3,
                          font=("Consolas", 12, "bold"), justify="center",
                          bg="#161b22", fg="#38bdf8", insertbackground="#38bdf8",
                          relief="solid", bd=1)
        mm_box.pack(side="left", padx=2)
        mm_box.bind("<MouseWheel>", lambda e: (_step_m(1 if getattr(e, "delta", 0) > 0 else -1), "break")[1])
        mm_box.bind("<Up>", lambda e: (_step_m(1), "break")[1])
        mm_box.bind("<Down>", lambda e: (_step_m(-1), "break")[1])
        mm_box.bind("<Enter>", lambda e: mm_box.focus_set())
        mm_box.bind("<FocusOut>", lambda e: _calc_delta())

        countdown_preview.pack(fill="x", pady=2)
        _calc_delta()

        btn_row = tk.Frame(panel, bg="#0d1117")
        btn_row.pack(fill="x", pady=(4, 0))

        def _set_clock_alarm():
            diff_s = _calc_delta()
            self._set_live_countdown_direct(diff_s)

        ttk.Button(btn_row, text="Set Alarm", command=_set_clock_alarm).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Cancel", command=self._close_quick_panel).pack(side="left", padx=2)

    def _reset_live_countdown(self):
        """Reset elapsed counter so countdown restarts from its full configured value."""
        self._reminder_elapsed = 0
        try:
            total = max(1, int(self.reminder_interval.get()))
        except (ValueError, TypeError):
            total = 2700
        rh, rr = divmod(total, 3600); rm, rs = divmod(rr, 60)
        self._countdown_var.set(f"{rh:02d}:{rm:02d}:{rs:02d}")

    def _toggle_reminder_enabled(self):
        """Toggle reminder master switch and update UI state."""
        self.reminder_enabled.set(not self.reminder_enabled.get())
        self._on_reminder_toggle()
        self.save_focus_sound_settings()

    # ── Inline Quick-Add Panel & Direct Edit (No Toplevel) ────────────────────

    def _on_countdown_click(self, event=None):
        """Single-click debouncer: wait briefly to distinguish from double-click."""
        self._reminder_tooltip_cancel()
        if getattr(self, "_countdown_click_job", None) is not None:
            self.root.after_cancel(self._countdown_click_job)
        self._countdown_click_job = self.root.after(220, self._open_quick_add_panel)

    def _on_countdown_double_click(self, event=None):
        """Double-click handler: cancel single-click and open direct edit."""
        self._reminder_tooltip_cancel()
        if getattr(self, "_countdown_click_job", None) is not None:
            self.root.after_cancel(self._countdown_click_job)
            self._countdown_click_job = None
        self._open_direct_edit_panel()

    def _close_quick_panel(self):
        """Close and destroy the inline floating panel, cleaning up root bindings."""
        if getattr(self, "_quick_dismiss_id", None):
            try:
                self.root.unbind("<Button-1>", self._quick_dismiss_id)
            except Exception:
                pass
            self._quick_dismiss_id = None
        if self._quick_panel:
            try:
                self._quick_panel.destroy()
            except Exception:
                pass
            self._quick_panel = None

    def _setup_outside_dismiss(self, panel):
        """Dismiss panel when the user clicks anywhere outside it."""
        def _on_root_click(e):
            if not self._quick_panel:
                return
            w = e.widget
            inside = False
            while w is not None:
                if w == self._quick_panel or w == self._reminder_interval_entry:
                    inside = True
                    break
                w = getattr(w, "master", None)
            if not inside:
                self._close_quick_panel()
        self._quick_dismiss_id = self.root.bind("<Button-1>", _on_root_click, add="+")

    def _get_panel_xy(self):
        """Calculate placement on the RIGHT side of the countdown label."""
        lbl = self._reminder_interval_entry
        lbl.update_idletasks()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        lbl_x = lbl.winfo_rootx()
        lbl_y = lbl.winfo_rooty()
        lbl_w = lbl.winfo_width()

        x = lbl_x - root_x + lbl_w + 6
        y = lbl_y - root_y
        root_w = self.root.winfo_width()
        if x + 240 > root_w:
            x = max(10, root_w - 245)
        return x, max(5, y)

    def _get_current_live_seconds(self):
        """Get the live remaining countdown seconds (or configured interval)."""
        try:
            total = max(1, int(self.reminder_interval.get()))
        except (ValueError, TypeError):
            total = 2700
        if self.session and self.session.get("status") == "active" and self.reminder_enabled.get():
            return max(0, total - getattr(self, "_reminder_elapsed", 0))
        return total

    def _apply_live_countdown_delta(self, delta_s):
        """Add or subtract delta seconds from live countdown and update immediately."""
        cur = self._get_current_live_seconds()
        new_val = max(1, cur + delta_s)
        self.reminder_interval.set(str(new_val))
        self._reminder_elapsed = 0
        rh, rr = divmod(new_val, 3600); rm, rs = divmod(rr, 60)
        self._countdown_var.set(f"{rh:02d}:{rm:02d}:{rs:02d}")
        self.save_focus_sound_settings()
        self._close_quick_panel()

    def _set_live_countdown_direct(self, total_s):
        """Set live countdown directly to a specified total seconds."""
        new_val = max(1, total_s)
        self.reminder_interval.set(str(new_val))
        self._reminder_elapsed = 0
        rh, rr = divmod(new_val, 3600); rm, rs = divmod(rr, 60)
        self._countdown_var.set(f"{rh:02d}:{rm:02d}:{rs:02d}")
        self.save_focus_sound_settings()
        self._close_quick_panel()

    @staticmethod
    def _format_preset_label(preset):
        sign = "+" if preset.get("sign", "+") != "-" else "-"
        sec = max(0, int(preset.get("seconds", 0)))
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        tag = preset.get("tag")
        prefix = f"{tag} " if tag else ""
        return f"{prefix}{sign}{h:02d}:{m:02d}:{s:02d}"

    def _build_hms_scroller(self, parent, initial_seconds=0):
        """Creates an inline HH:MM:SS scroller frame with mousewheel support.
        Returns (frame, get_seconds_func).
        """
        init_s = max(0, int(initial_seconds))
        h_val, rem = divmod(init_s, 3600)
        m_val, s_val = divmod(rem, 60)
        h_val = min(99, h_val)

        scroller_frame = tk.Frame(parent, bg="#0d1117")

        h_var = tk.StringVar(value=f"{h_val:02d}")
        m_var = tk.StringVar(value=f"{m_val:02d}")
        s_var = tk.StringVar(value=f"{s_val:02d}")

        def _step(var, delta, min_v, max_v, wrap):
            try:
                cur = int(var.get())
            except (ValueError, TypeError):
                cur = 0
            if wrap:
                new_v = (cur + delta) % (max_v + 1)
                if new_v < min_v:
                    new_v = max_v
            else:
                new_v = max(min_v, min(max_v, cur + delta))
            var.set(f"{new_v:02d}")

        def _bind_segment(widget, var, min_v, max_v, wrap):
            def _on_wheel(e):
                delta = 1 if getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4 else -1
                _step(var, delta, min_v, max_v, wrap)
                return "break"

            widget.bind("<MouseWheel>", _on_wheel)
            widget.bind("<Button-4>", _on_wheel)
            widget.bind("<Button-5>", _on_wheel)
            widget.bind("<Up>", lambda e: (_step(var, 1, min_v, max_v, wrap), "break")[1])
            widget.bind("<Down>", lambda e: (_step(var, -1, min_v, max_v, wrap), "break")[1])
            widget.bind("<Enter>", lambda e, w=widget: w.focus_set())

            def _on_focus_out(e):
                try:
                    v = int(var.get())
                    if wrap and max_v == 59:
                        v = v % 60
                    else:
                        v = max(min_v, min(max_v, v))
                except (ValueError, TypeError):
                    v = 0
                var.set(f"{v:02d}")
            widget.bind("<FocusOut>", _on_focus_out)

        digits_row = tk.Frame(scroller_frame, bg="#0d1117")
        digits_row.pack(pady=(2, 0))

        # HH Box (00-99)
        hh_box = tk.Entry(digits_row, textvariable=h_var, width=3,
                          font=("Consolas", 12, "bold"), justify="center",
                          bg="#161b22", fg="#38bdf8", insertbackground="#38bdf8",
                          relief="solid", bd=1)
        hh_box.pack(side="left", padx=1)
        _bind_segment(hh_box, h_var, 0, 99, wrap=False)

        tk.Label(digits_row, text=":", font=("Consolas", 12, "bold"),
                 bg="#0d1117", fg="#94a3b8").pack(side="left")

        # MM Box (00-59)
        mm_box = tk.Entry(digits_row, textvariable=m_var, width=3,
                          font=("Consolas", 12, "bold"), justify="center",
                          bg="#161b22", fg="#38bdf8", insertbackground="#38bdf8",
                          relief="solid", bd=1)
        mm_box.pack(side="left", padx=1)
        _bind_segment(mm_box, m_var, 0, 59, wrap=True)

        tk.Label(digits_row, text=":", font=("Consolas", 12, "bold"),
                 bg="#0d1117", fg="#94a3b8").pack(side="left")

        # SS Box (00-59)
        ss_box = tk.Entry(digits_row, textvariable=s_var, width=3,
                          font=("Consolas", 12, "bold"), justify="center",
                          bg="#161b22", fg="#38bdf8", insertbackground="#38bdf8",
                          relief="solid", bd=1)
        ss_box.pack(side="left", padx=1)
        _bind_segment(ss_box, s_var, 0, 59, wrap=True)

        # Labels row: HH  MM  SS
        sub_row = tk.Frame(scroller_frame, bg="#0d1117")
        sub_row.pack(fill="x", pady=(1, 2))
        tk.Label(sub_row, text="HH", font=("Segoe UI", 7), bg="#0d1117", fg="#64748b", width=4).pack(side="left", padx=1)
        tk.Label(sub_row, text=" ", bg="#0d1117", width=1).pack(side="left")
        tk.Label(sub_row, text="MM", font=("Segoe UI", 7), bg="#0d1117", fg="#64748b", width=4).pack(side="left", padx=1)
        tk.Label(sub_row, text=" ", bg="#0d1117", width=1).pack(side="left")
        tk.Label(sub_row, text="SS", font=("Segoe UI", 7), bg="#0d1117", fg="#64748b", width=4).pack(side="left", padx=1)

        def get_total_seconds():
            try: h = int(h_var.get())
            except Exception: h = 0
            try: m = int(m_var.get())
            except Exception: m = 0
            try: s = int(s_var.get())
            except Exception: s = 0
            return h * 3600 + m * 60 + s

        return scroller_frame, get_total_seconds

    def _open_quick_add_panel(self):
        """Single-click on countdown: open inline quick-add panel on the RIGHT SIDE."""
        self._countdown_click_job = None
        if self._quick_panel:
            self._close_quick_panel()
            return

        x, y = self._get_panel_xy()
        panel = tk.Frame(self.root, relief="solid", bd=1, bg="#0d1117",
                         highlightbackground="#30363d", highlightthickness=1,
                         padx=8, pady=8)
        panel.place(x=x, y=y)
        self._quick_panel = panel
        self._setup_outside_dismiss(panel)
        self._render_presets_view()

    def _render_presets_view(self):
        """Render the 4 preset buttons + 1 Custom button inside the quick panel."""
        if not self._quick_panel:
            return
        for child in self._quick_panel.winfo_children():
            child.destroy()

        header = tk.Label(self._quick_panel, text="Quick Add Time",
                          font=("Segoe UI", 9, "bold"), bg="#0d1117", fg="#94a3b8")
        header.pack(anchor="w", pady=(0, 4))

        # Grid of presets (2 columns, up to 4 buttons)
        grid_frame = tk.Frame(self._quick_panel, bg="#0d1117")
        grid_frame.pack(fill="x")

        presets = getattr(self, "_timer_presets", [])
        for i, p in enumerate(presets[:4]):
            r, c = divmod(i, 2)
            lbl_text = self._format_preset_label(p)
            btn = ttk.Button(grid_frame, text=lbl_text, width=13)
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="ew")

            delta = p["seconds"] if p.get("sign", "+") != "-" else -p["seconds"]
            btn.configure(command=lambda d=delta: self._apply_live_countdown_delta(d))

            # Right click context menu for this specific preset button
            btn.bind("<Button-3>", lambda e, idx=i: self._show_preset_context_menu(e, idx))
            btn.bind("<Button-2>", lambda e, idx=i: self._show_preset_context_menu(e, idx))

        if len(presets) < 4:
            add_slot = ttk.Button(grid_frame, text="＋ Add Preset", width=13,
                                  command=lambda: self._render_add_custom_box_view())
            r, c = divmod(len(presets), 2)
            add_slot.grid(row=r, column=c, padx=3, pady=3, sticky="ew")

        ttk.Separator(self._quick_panel, orient="horizontal").pack(fill="x", pady=6)

        # 5th button: Custom Button
        custom_btn = ttk.Button(self._quick_panel, text="✎ Custom",
                                command=self._render_custom_view)
        custom_btn.pack(fill="x", padx=3)

    def _show_preset_context_menu(self, event, index):
        """Show context menu specifically for the right-clicked preset button."""
        if not (0 <= index < len(getattr(self, "_timer_presets", []))):
            return
        menu = tk.Menu(self.root, tearoff=0, bg="#161b22", fg="#e6edf3",
                       activebackground="#1f6feb", activeforeground="#ffffff",
                       relief="solid", bd=1)
        menu.add_command(label="⭐ Set as Default Interval",
                         command=lambda: self._set_preset_as_default(index))

        # Move reordering
        if index > 0:
            menu.add_command(label="◀ Move Left",
                             command=lambda: self._move_preset(index, -1))
        if index < len(self._timer_presets) - 1:
            menu.add_command(label="▶ Move Right",
                             command=lambda: self._move_preset(index, 1))

        # Activity Tag submenu
        tag_menu = tk.Menu(menu, tearoff=0, bg="#161b22", fg="#e6edf3",
                           activebackground="#1f6feb", activeforeground="#ffffff")
        cur_tag = self._timer_presets[index].get("tag", "")
        tags = [
            ("☕ Break", "☕"),
            ("🧘 Stretch", "🧘"),
            ("⚡ Sprint", "⚡"),
            ("🎯 Deep Work", "🎯"),
            ("None (Clear Tag)", None),
        ]
        for label, tag_val in tags:
            prefix = "✓ " if cur_tag == (tag_val or "") else "   "
            tag_menu.add_command(
                label=prefix + label,
                command=lambda t=tag_val: self._set_preset_tag(index, t)
            )
        menu.add_cascade(label="🏷 Activity Tag", menu=tag_menu)

        menu.add_separator()
        menu.add_command(label="✏️ Edit Duration...",
                         command=lambda: self._render_edit_preset_view(index))
        menu.add_command(label="± Change Sign (+ / -)",
                         command=lambda: self._toggle_preset_sign(index))
        menu.add_command(label="🗑 Remove Preset",
                         command=lambda: self._remove_preset(index))
        menu.add_command(label="➕ Add New Preset...",
                         command=lambda: self._render_add_custom_box_view(replace_index=index))
        menu.tk_popup(event.x_root, event.y_root)

    def _set_preset_as_default(self, index):
        """Set this preset's duration as the default starting reminder interval."""
        if 0 <= index < len(self._timer_presets):
            sec = self._timer_presets[index].get("seconds", 2700)
            self._set_live_countdown_direct(sec)

    def _move_preset(self, index, direction):
        """Move preset left (-1) or right (+1) in the list."""
        new_idx = index + direction
        if 0 <= index < len(self._timer_presets) and 0 <= new_idx < len(self._timer_presets):
            self._timer_presets[index], self._timer_presets[new_idx] = (
                self._timer_presets[new_idx], self._timer_presets[index]
            )
            self.save_focus_sound_settings()
            self._render_presets_view()

    def _set_preset_tag(self, index, tag):
        """Set or remove activity tag on preset button."""
        if 0 <= index < len(self._timer_presets):
            if tag:
                self._timer_presets[index]["tag"] = tag
            else:
                self._timer_presets[index].pop("tag", None)
            self.save_focus_sound_settings()
            self._render_presets_view()

    def _toggle_preset_sign(self, index):
        """Toggle the sign (+ <-> -) of the specified preset."""
        if 0 <= index < len(self._timer_presets):
            cur = self._timer_presets[index].get("sign", "+")
            self._timer_presets[index]["sign"] = "-" if cur == "+" else "+"
            self.save_focus_sound_settings()
            self._render_presets_view()

    def _remove_preset(self, index):
        """Remove the specified preset button."""
        if 0 <= index < len(self._timer_presets):
            del self._timer_presets[index]
            self.save_focus_sound_settings()
            self._render_presets_view()

    def _render_edit_preset_view(self, index):
        """Inline view to edit duration and sign for a preset button."""
        if not self._quick_panel or not (0 <= index < len(self._timer_presets)):
            return
        for child in self._quick_panel.winfo_children():
            child.destroy()

        preset = self._timer_presets[index]
        cur_sign = preset.get("sign", "+")
        cur_sec = preset.get("seconds", 900)

        header = tk.Label(self._quick_panel, text=f"Edit Preset #{index + 1}",
                          font=("Segoe UI", 9, "bold"), bg="#0d1117", fg="#38bdf8")
        header.pack(anchor="w", pady=(0, 4))

        sign_row = tk.Frame(self._quick_panel, bg="#0d1117")
        sign_row.pack(fill="x", pady=2)
        tk.Label(sign_row, text="Sign:", bg="#0d1117", fg="#94a3b8", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))

        sign_var = tk.StringVar(value="+" if cur_sign != "-" else "-")
        sign_btn = tk.Button(sign_row, textvariable=sign_var,
                             font=("Consolas", 10, "bold"), width=4,
                             bg="#21262d", fg="#58a6ff", relief="solid", bd=1)
        sign_btn.configure(command=lambda: sign_var.set("-" if sign_var.get() == "+" else "+"))
        sign_btn.pack(side="left")

        scroller, get_sec = self._build_hms_scroller(self._quick_panel, initial_seconds=cur_sec)
        scroller.pack(fill="x", pady=4)

        btn_row = tk.Frame(self._quick_panel, bg="#0d1117")
        btn_row.pack(fill="x", pady=(4, 0))

        def _save():
            new_s = max(1, get_sec())
            new_sign = "-" if sign_var.get() == "-" else "+"
            self._timer_presets[index] = {"sign": new_sign, "seconds": new_s}
            self.save_focus_sound_settings()
            self._render_presets_view()

        ttk.Button(btn_row, text="Save", command=_save).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Cancel", command=self._render_presets_view).pack(side="left", padx=2)

    def _render_add_custom_box_view(self, replace_index=None):
        """Inline view to add/create a custom timer preset."""
        if not self._quick_panel:
            return
        for child in self._quick_panel.winfo_children():
            child.destroy()

        header = tk.Label(self._quick_panel, text="Add Timer Preset",
                          font=("Segoe UI", 9, "bold"), bg="#0d1117", fg="#38bdf8")
        header.pack(anchor="w", pady=(0, 4))

        sign_row = tk.Frame(self._quick_panel, bg="#0d1117")
        sign_row.pack(fill="x", pady=2)
        tk.Label(sign_row, text="Sign:", bg="#0d1117", fg="#94a3b8", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))

        sign_var = tk.StringVar(value="+")
        sign_btn = tk.Button(sign_row, textvariable=sign_var,
                             font=("Consolas", 10, "bold"), width=4,
                             bg="#21262d", fg="#58a6ff", relief="solid", bd=1)
        sign_btn.configure(command=lambda: sign_var.set("-" if sign_var.get() == "+" else "+"))
        sign_btn.pack(side="left")

        scroller, get_sec = self._build_hms_scroller(self._quick_panel, initial_seconds=900)
        scroller.pack(fill="x", pady=4)

        btn_row = tk.Frame(self._quick_panel, bg="#0d1117")
        btn_row.pack(fill="x", pady=(4, 0))

        def _add():
            new_s = max(1, get_sec())
            new_sign = "-" if sign_var.get() == "-" else "+"
            new_item = {"sign": new_sign, "seconds": new_s}
            if len(self._timer_presets) < 4:
                self._timer_presets.append(new_item)
            elif replace_index is not None and 0 <= replace_index < len(self._timer_presets):
                self._timer_presets[replace_index] = new_item
            else:
                self._timer_presets[0] = new_item
            self.save_focus_sound_settings()
            self._render_presets_view()

        ttk.Button(btn_row, text="Add", command=_add).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Cancel", command=self._render_presets_view).pack(side="left", padx=2)

    def _render_custom_view(self):
        """Inline view for the 5th Custom button to add/subtract custom time."""
        if not self._quick_panel:
            return
        for child in self._quick_panel.winfo_children():
            child.destroy()

        header = tk.Label(self._quick_panel, text="Custom Time (Scroll HH:MM:SS)",
                          font=("Segoe UI", 9, "bold"), bg="#0d1117", fg="#94a3b8")
        header.pack(anchor="w", pady=(0, 4))

        is_add = tk.BooleanVar(value=True)
        mode_btn = tk.Button(self._quick_panel, text="+ Add to Countdown",
                             font=("Segoe UI", 9, "bold"), bg="#238636", fg="#ffffff",
                             activebackground="#2ea043", relief="flat", padx=6, pady=2)
        def _toggle_mode():
            if is_add.get():
                is_add.set(False)
                mode_btn.configure(text="- Subtract from Countdown", bg="#da3633", activebackground="#f85149")
            else:
                is_add.set(True)
                mode_btn.configure(text="+ Add to Countdown", bg="#238636", activebackground="#2ea043")
        mode_btn.configure(command=_toggle_mode)
        mode_btn.pack(fill="x", pady=2)

        scroller, get_sec = self._build_hms_scroller(self._quick_panel, initial_seconds=900)
        scroller.pack(fill="x", pady=4)

        btn_row = tk.Frame(self._quick_panel, bg="#0d1117")
        btn_row.pack(fill="x", pady=(4, 0))

        def _apply():
            s = get_sec()
            delta = s if is_add.get() else -s
            self._apply_live_countdown_delta(delta)

        ttk.Button(btn_row, text="Apply", command=_apply).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Back", command=self._render_presets_view).pack(side="left", padx=2)

    def _open_direct_edit_panel(self):
        """Double-click on countdown: directly edit the live countdown inline."""
        self._countdown_click_job = None
        if self._quick_panel:
            self._close_quick_panel()

        x, y = self._get_panel_xy()
        panel = tk.Frame(self.root, relief="solid", bd=1, bg="#0d1117",
                         highlightbackground="#30363d", highlightthickness=1,
                         padx=8, pady=8)
        panel.place(x=x, y=y)
        self._quick_panel = panel
        self._setup_outside_dismiss(panel)

        header = tk.Label(panel, text="Direct Edit Countdown",
                          font=("Segoe UI", 9, "bold"), bg="#0d1117", fg="#38bdf8")
        header.pack(anchor="w", pady=(0, 4))

        cur_sec = self._get_current_live_seconds()
        scroller, get_sec = self._build_hms_scroller(panel, initial_seconds=cur_sec)
        scroller.pack(fill="x", pady=4)

        btn_row = tk.Frame(panel, bg="#0d1117")
        btn_row.pack(fill="x", pady=(4, 0))

        def _set_direct(e=None):
            new_s = max(1, get_sec())
            self._set_live_countdown_direct(new_s)

        ttk.Button(btn_row, text="Set", command=_set_direct).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Cancel", command=self._close_quick_panel).pack(side="left", padx=2)
        panel.bind("<Return>", _set_direct)

    def _toggle_settings(self):
        """Show/hide the collapsible Sound Settings panel."""
        if self._settings_open:
            self._settings_frame.pack_forget()
            self._settings_btn.configure(text="⚙ Settings ▸")
        else:
            self._settings_frame.pack(fill="x", pady=(4, 0))
            self._settings_btn.configure(text="⚙ Settings ▾")
        self._settings_open = not self._settings_open

    def _update_sound_buttons(self):
        """Update visual styling of Play and Pause buttons so user knows sound is on."""
        if not hasattr(self, "_play_btn") or not hasattr(self, "_pause_btn"):
            return
        t = THEMES.get(getattr(self, "current_theme", "amoled"), THEMES["amoled"])
        is_enabled = self.reminder_enabled.get()
        is_active = getattr(self, "_test_playing", False) or (hasattr(self, "sound_engine") and self.sound_engine.is_playing)

        if not is_enabled:
            self._play_btn.configure(
                text="▶ Play", state="disabled",
                bg=t["card_bg"], fg=t["muted"],
                activebackground=t["card_bg"], activeforeground=t["muted"]
            )
            self._pause_btn.configure(
                text="⏸ Pause", state="disabled",
                bg=t["card_bg"], fg=t["muted"],
                activebackground=t["card_bg"], activeforeground=t["muted"]
            )
        elif is_active:
            # Sound is ON: Make Play button vibrant green with white text so user clearly knows it's playing!
            self._play_btn.configure(
                text="🔊 Playing ●", state="normal",
                bg="#238636", fg="#ffffff",
                activebackground="#2ea043", activeforeground="#ffffff"
            )
            self._pause_btn.configure(
                text="⏸ Pause", state="normal",
                bg="#da3633", fg="#ffffff",
                activebackground="#f85149", activeforeground="#ffffff"
            )
        else:
            # Sound is OFF / IDLE: standard clean theme styling
            self._play_btn.configure(
                text="▶ Play", state="normal",
                bg=t["card_bg"], fg=t["accent"],
                activebackground=t["border"], activeforeground=t["accent_text"]
            )
            self._pause_btn.configure(
                text="⏸ Pause", state="disabled",
                bg=t["card_bg"], fg=t["muted"],
                activebackground=t["card_bg"], activeforeground=t["muted"]
            )

    def _toggle_test_sound(self):
        """Toggle test sound on or off immediately on click."""
        if getattr(self, "_test_playing", False) or (hasattr(self, "sound_engine") and self.sound_engine.is_playing):
            self._pause_test()
        else:
            self._play_test()

    def _play_test(self):
        """Start test sound playing indefinitely with instant visual feedback."""
        FocusSoundEngine._check_libs()
        mode = self.sound_mode.get()
        if mode == "sine" and not FocusSoundEngine._sd_ok:
            messagebox.showinfo("Missing libraries",
                                FocusSoundEngine.missing_libs_message("sine"), parent=self.root)
            return
        if mode == "mp3" and not FocusSoundEngine._pg_ok:
            messagebox.showinfo("Missing libraries",
                                FocusSoundEngine.missing_libs_message("mp3"), parent=self.root)
            return
        self._test_playing = True
        self._update_sound_buttons()       # immediate UI color change (0ms)
        self.sound_engine.stop()
        self.sound_engine.play()          # no duration_s -> plays until stopped
        self.save_focus_sound_settings()

    def _pause_test(self):
        """Pause (stop) the test sound immediately with instant visual feedback."""
        self._test_playing = False
        self._update_sound_buttons()       # immediate UI color change (0ms)
        self.sound_engine.stop()

    def _on_reminder_toggle(self):
        """Grey out controls when reminder is disabled; save on every change."""
        enabled = self.reminder_enabled.get()
        state = "normal" if enabled else "disabled"
        for w in self._sound_controls():
            try: w.configure(state=state)
            except Exception: pass
        if getattr(self, "_settings_btn", None):
            try: self._settings_btn.configure(state=state)
            except Exception: pass
        if not enabled:
            self._pause_test()
        self._update_sound_buttons()
        if hasattr(self, "sound_engine"):
            self.save_focus_sound_settings()

    def _sound_controls(self):
        """Return reminder-related widgets for bulk enable/disable."""
        widgets = []
        if hasattr(self, "_reminder_interval_entry"):
            widgets.append(self._reminder_interval_entry)
        for frame in (getattr(self, "_freq_frame", None),
                      getattr(self, "_mp3_frame", None),
                      getattr(self, "_settings_frame", None)):
            if frame:
                try:
                    for child in frame.winfo_children():
                        widgets.append(child)
                        # recurse one level for nested frames
                        try:
                            for gc in child.winfo_children():
                                widgets.append(gc)
                        except Exception:
                            pass
                except Exception:
                    pass
        return widgets

    def _on_sound_mode_change(self):
        """Show freq entries for sine mode, MP3 path for mp3 mode (inside settings panel)."""
        mode = self.sound_mode.get()
        if mode == "sine":
            self._freq_frame.pack(side="left", padx=(12, 0))
            self._mp3_frame.pack_forget()
        else:
            self._freq_frame.pack_forget()
            self._mp3_frame.pack(side="left")
        if hasattr(self, "sound_engine"):
            self.save_focus_sound_settings()

    def _browse_mp3(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Select MP3 file",
            filetypes=[("Audio files", "*.mp3 *.wav *.ogg *.flac"), ("All files", "*.*")]
        )
        if path:
            self.mp3_path.set(path)
            self.save_focus_sound_settings()

    def _fire_reminder(self):
        """Called when the study reminder countdown reaches zero."""
        chime_mode = self.data.get("_settings", {}).get("focus_sound", {}).get("chime_mode", "once")
        if chime_mode != "silent":
            FocusSoundEngine._check_libs()
            mode = self.sound_mode.get()
            if mode == "sine" and not FocusSoundEngine._sd_ok:
                messagebox.showinfo("Missing libraries",
                                    FocusSoundEngine.missing_libs_message("sine"), parent=self.root)
                return
            if mode == "mp3" and not FocusSoundEngine._pg_ok:
                messagebox.showinfo("Missing libraries",
                                    FocusSoundEngine.missing_libs_message("mp3"), parent=self.root)
                return
            self.sound_engine.stop()
            if chime_mode == "loop":
                self.sound_engine.play()  # plays until stopped
                self._test_playing = True
                self._update_sound_buttons()
            else:
                self.sound_engine.play(duration_s=3)
                self._test_playing = True
                self._update_sound_buttons()
                self.root.after(3200, lambda: (setattr(self, "_test_playing", False), self._update_sound_buttons()))
        self._show_reminder_toast(is_loop=(chime_mode == "loop"))

    def _show_reminder_toast(self, is_loop=False):
        """Flash a reminder banner centred on the app window with click-to-dismiss."""
        try:
            toast = tk.Toplevel(self.root)
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)
            rx = self.root.winfo_x() + self.root.winfo_width() // 2
            ry = self.root.winfo_y() + self.root.winfo_height() // 2
            toast.geometry(f"340x58+{rx - 170}+{ry - 29}")
            sub_text = "Click to stop chime & dismiss" if is_loop else "Click to dismiss"
            lbl = tk.Label(toast, text=f"🔔  Study Reminder — time for a break!\n({sub_text})",
                           font=("Segoe UI", 10, "bold"), padx=12, pady=8,
                           bg="#1e293b", fg="#38bdf8", cursor="hand2")
            lbl.pack(fill="both", expand=True)

            def _dismiss(e=None):
                self._test_playing = False
                self.sound_engine.stop()
                self._update_sound_buttons()
                try: toast.destroy()
                except Exception: pass

            lbl.bind("<Button-1>", _dismiss)
            toast.bind("<Button-1>", _dismiss)

            if not is_loop:
                toast.after(4000, lambda: (setattr(self, "_test_playing", False), self._update_sound_buttons(), toast.destroy()))
        except Exception:
            pass

    # ── End Focus Sound helpers ──────────────────────────────────────────────




    def check_first_run(self):

        settings = self.data.get("_settings", {})
        if "player_mode" not in settings:
            self.first_run_dialog()

    def first_run_dialog(self):
        window = tk.Toplevel(self.root)
        window.title("Welcome - Select Your Media Player")
        window.geometry("580x440")
        window.transient(self.root)
        window.grab_set()

        f = ttk.Frame(window, padding=16)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="Welcome to Lecture Progress Tracker!", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(f, text="Which media player do you primarily use for watching your lectures?\nYou can change this or adjust ports anytime in Player Settings.", wraplength=540, foreground="#444").pack(anchor="w", pady=(6, 12))

        mode_var = tk.StringVar(value=PLAYER_MODE)
        priority_var = tk.StringVar(value=PRIORITY_PLAYER)

        ttk.Radiobutton(f, text="Auto-detect (Recommended - works with both MPC-BE & VLC)", variable=mode_var, value="auto").pack(anchor="w", pady=3)
        ttk.Radiobutton(f, text="MPC-BE only (port 13579)", variable=mode_var, value="mpc").pack(anchor="w", pady=3)
        ttk.Radiobutton(f, text="VLC Media Player only (port 8080)", variable=mode_var, value="vlc").pack(anchor="w", pady=3)

        p_frame = ttk.LabelFrame(f, text="When both players are open in Auto-detect, prioritize:", padding=8)
        p_frame.pack(fill="x", pady=12)
        ttk.Radiobutton(p_frame, text="Prioritize MPC-BE", variable=priority_var, value="mpc").pack(side="left", padx=(10, 20))
        ttk.Radiobutton(p_frame, text="Prioritize VLC", variable=priority_var, value="vlc").pack(side="left")

        guide_lbl = ttk.Label(f, text="Need help enabling the web interface in MPC-BE or VLC? Click to open Setup Guide.", foreground="#1a73e8", cursor="hand2")
        guide_lbl.pack(anchor="w", pady=(8, 4))
        guide_lbl.bind("<Button-1>", lambda e: self.open_help_guide())

        def on_save():
            self.save_player_settings(mode_var.get(), priority_var.get(), MPC_PORT, VLC_PORT, VLC_PASSWORD)
            window.destroy()

        b_row = ttk.Frame(f)
        b_row.pack(fill="x", side="bottom", pady=(10, 0))
        ttk.Button(b_row, text="📖 Open Setup Guide", command=self.open_help_guide).pack(side="left")
        ttk.Button(b_row, text="Save Preference", command=on_save).pack(side="right")

    def open_settings(self, initial_tab="pref"):
        window = tk.Toplevel(self.root)
        window.title("GitVLMPC Settings")
        window.geometry("680x620")
        window.transient(self.root)
        window.grab_set()

        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        pref_tab = ttk.Frame(notebook, padding=16)
        notebook.add(pref_tab, text="  ⚙ Player Preferences  ")

        theme_tab = ttk.Frame(notebook, padding=16)
        notebook.add(theme_tab, text="  🎨 Appearance & Theme  ")

        # --- Tab 1: Preferences ---
        ttk.Label(pref_tab, text="Media Player & Detection", font=("Segoe UI", 12, "bold")).pack(anchor="w")

        mode_var = tk.StringVar(value=PLAYER_MODE)
        priority_var = tk.StringVar(value=PRIORITY_PLAYER)
        mpc_port_var = tk.StringVar(value=str(MPC_PORT))
        vlc_port_var = tk.StringVar(value=str(VLC_PORT))
        vlc_pass_var = tk.StringVar(value=str(VLC_PASSWORD))

        m_frame = ttk.LabelFrame(pref_tab, text="Detection Mode", padding=10)
        m_frame.pack(fill="x", pady=(8, 8))
        ttk.Radiobutton(m_frame, text="Auto-detect (Automatically tracks whichever player is active)", variable=mode_var, value="auto").pack(anchor="w")
        ttk.Radiobutton(m_frame, text="MPC-BE only", variable=mode_var, value="mpc").pack(anchor="w", pady=2)
        ttk.Radiobutton(m_frame, text="VLC Media Player only", variable=mode_var, value="vlc").pack(anchor="w")

        p_frame = ttk.LabelFrame(pref_tab, text="Auto-detect Priority (if both players are open)", padding=10)
        p_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(p_frame, text="Prioritize MPC-BE", variable=priority_var, value="mpc").pack(side="left", padx=(10, 20))
        ttk.Radiobutton(p_frame, text="Prioritize VLC", variable=priority_var, value="vlc").pack(side="left")

        mpc_box = ttk.LabelFrame(pref_tab, text="MPC-BE Configuration", padding=10)
        mpc_box.pack(fill="x", pady=(0, 8))
        ttk.Label(mpc_box, text="Web Port:").grid(row=0, column=0, sticky="w")
        ttk.Entry(mpc_box, textvariable=mpc_port_var, width=12).grid(row=0, column=1, padx=8, sticky="w")
        def test_mpc_btn():
            try: p = int(mpc_port_var.get())
            except: messagebox.showerror("Invalid port", "Enter a valid port number.", parent=window); return
            ok, msg = test_mpc_conn(p)
            (messagebox.showinfo if ok else messagebox.showwarning)("MPC-BE Test", msg, parent=window)
        ttk.Button(mpc_box, text="Test MPC-BE", command=test_mpc_btn).grid(row=0, column=2, padx=10)

        vlc_box = ttk.LabelFrame(pref_tab, text="VLC Media Player Configuration", padding=10)
        vlc_box.pack(fill="x", pady=(0, 8))
        ttk.Label(vlc_box, text="Web Port:").grid(row=0, column=0, sticky="w")
        ttk.Entry(vlc_box, textvariable=vlc_port_var, width=12).grid(row=0, column=1, padx=8, sticky="w")
        ttk.Label(vlc_box, text="Lua Password:").grid(row=1, column=0, sticky="w", pady=(6,0))
        ttk.Entry(vlc_box, textvariable=vlc_pass_var, width=20, show="*").grid(row=1, column=1, padx=8, pady=(6,0), sticky="w")
        def test_vlc_btn():
            try: p = int(vlc_port_var.get())
            except: messagebox.showerror("Invalid port", "Enter a valid port number.", parent=window); return
            ok, msg = test_vlc_conn(p, vlc_pass_var.get())
            (messagebox.showinfo if ok else messagebox.showwarning)("VLC Test", msg, parent=window)
        ttk.Button(vlc_box, text="Test VLC", command=test_vlc_btn).grid(row=0, column=2, rowspan=2, padx=10)

        # --- Tab 2: Theme Settings ---
        ttk.Label(theme_tab, text="User Interface Theme", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(theme_tab, text="Select your preferred aesthetic. Live preview applies immediately.", font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 10))

        orig_theme = self.current_theme
        theme_var = tk.StringVar(value=self.current_theme)

        theme_box = ttk.LabelFrame(theme_tab, text="Choose Palette", padding=12)
        theme_box.pack(fill="x", pady=(0, 12))

        preview_frame = ttk.LabelFrame(theme_tab, text="Live Theme Preview", padding=12)
        preview_frame.pack(fill="both", expand=True)

        preview_canvas = tk.Canvas(preview_frame, height=140, highlightthickness=1)
        preview_canvas.pack(fill="both", expand=True, pady=4)

        def update_preview_canvas():
            curr = theme_var.get()
            t_data = THEMES.get(curr, THEMES["amoled"])
            preview_canvas.configure(bg=t_data["bg"], highlightbackground=t_data["border"])
            preview_canvas.delete("all")
            # Draw preview card
            preview_canvas.create_rectangle(16, 16, 320, 124, fill=t_data["card_bg"], outline=t_data["border"], width=1)
            preview_canvas.create_text(30, 36, text=f"Theme: {t_data['name']}", anchor="w", fill=t_data["fg"], font=("Segoe UI", 10, "bold"))
            preview_canvas.create_rectangle(30, 56, 180, 84, fill=t_data["tree_watched"], outline=t_data["border"])
            preview_canvas.create_text(40, 70, text="✓ Watched Lecture", anchor="w", fill=t_data["fg"], font=("Segoe UI", 8, "bold"))
            preview_canvas.create_rectangle(190, 56, 305, 84, fill=t_data["stopwatch_bg"], outline=t_data["border"])
            preview_canvas.create_text(202, 70, text="01:24:35", anchor="w", fill=t_data["stopwatch_fg"], font=("Consolas", 10, "bold"))
            preview_canvas.create_rectangle(30, 92, 180, 114, fill=t_data["tree_progress"], outline=t_data["border"])
            preview_canvas.create_text(40, 103, text="◐ In Progress", anchor="w", fill=t_data["fg"], font=("Segoe UI", 8))
            # Palette swatches
            preview_canvas.create_oval(350, 24, 380, 54, fill=t_data["accent"], outline=t_data["border"])
            preview_canvas.create_text(390, 39, text="Accent / Active color", anchor="w", fill=t_data["fg"], font=("Segoe UI", 9))
            preview_canvas.create_oval(350, 62, 380, 92, fill=t_data["card_bg"], outline=t_data["border"])
            preview_canvas.create_text(390, 77, text="Card / Panel surface", anchor="w", fill=t_data["fg"], font=("Segoe UI", 9))
            preview_canvas.create_oval(350, 100, 380, 130, fill=t_data["bg"], outline=t_data["border"])
            preview_canvas.create_text(390, 115, text="Background", anchor="w", fill=t_data["fg"], font=("Segoe UI", 9))

        def on_theme_change():
            sel = theme_var.get()
            self.apply_theme(sel)
            update_preview_canvas()

        ttk.Radiobutton(theme_box, text="🌓 Minimalist Light (Clean Notion/Apple style, crisp typography, white cards)",
                        variable=theme_var, value="light", command=on_theme_change).pack(anchor="w", pady=4)
        ttk.Radiobutton(theme_box, text="🖤 AMOLED Dark (Pitch black #000000 for OLED, glowing cyan stopwatch & high contrast)",
                        variable=theme_var, value="amoled", command=on_theme_change).pack(anchor="w", pady=4)

        update_preview_canvas()

        # Bottom Bar
        b_row = ttk.Frame(window, padding=(12, 6, 12, 12))
        b_row.pack(fill="x", side="bottom")
        ttk.Button(b_row, text="📖 Setup Guide", command=self.open_help_guide).pack(side="left")

        def save_and_close():
            try:
                mp = int(mpc_port_var.get())
                vp = int(vlc_port_var.get())
                if not (1 <= mp <= 65535 and 1 <= vp <= 65535): raise ValueError
            except ValueError:
                messagebox.showerror("Invalid port", "Ports must be numbers between 1 and 65535.", parent=window)
                return
            self.save_player_settings(mode_var.get(), priority_var.get(), mp, vp, vlc_pass_var.get())
            chosen_theme = theme_var.get()
            self.apply_theme(chosen_theme)
            save_app_theme(chosen_theme)
            window.destroy()

        def on_cancel():
            self.apply_theme(orig_theme)
            window.destroy()

        ttk.Button(b_row, text="Cancel", command=on_cancel).pack(side="right", padx=(6, 0))
        ttk.Button(b_row, text="Save Settings", command=save_and_close).pack(side="right")

        if initial_tab == "theme":
            notebook.select(theme_tab)
        else:
            notebook.select(pref_tab)

    def configure_player(self):
        self.open_settings("pref")

    def test_player(self):
        if PLAYER_MODE == "mpc":
            ok, msg = test_mpc_conn()
            (messagebox.showinfo if ok else messagebox.showwarning)("MPC-BE Connection", msg, parent=self.root)
        elif PLAYER_MODE == "vlc":
            ok, msg = test_vlc_conn()
            (messagebox.showinfo if ok else messagebox.showwarning)("VLC Connection", msg, parent=self.root)
        else:
            m_ok, m_msg = test_mpc_conn()
            v_ok, v_msg = test_vlc_conn()
            status_text = (
                f"Auto-detect Results (Priority: {PRIORITY_PLAYER.upper()}):\n\n"
                f"• MPC-BE (port {MPC_PORT}): {'Connected ✓' if m_ok else 'Not reachable ✗'}\n"
                f"• VLC (port {VLC_PORT}): {'Connected ✓' if v_ok else 'Not reachable ✗'}\n\n"
                f"MPC-BE details:\n{m_msg}\n\n"
                f"VLC details:\n{v_msg}"
            )
            (messagebox.showinfo if (m_ok or v_ok) else messagebox.showwarning)("Player Test Results", status_text, parent=self.root)

    def open_help_guide(self, initial_tab=None):
        window = tk.Toplevel(self.root)
        window.title("Media Player Setup & Help Guide")
        window.geometry("740x630")
        window.transient(self.root)

        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        mpc_tab = ttk.Frame(notebook, padding=16)
        notebook.add(mpc_tab, text="  MPC-BE Setup  ")

        ttk.Label(mpc_tab, text="How to Configure MPC-BE", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        mpc_instructions = (
            "MPC-BE has a built-in web interface that allows the tracker to read playback position.\n\n"
            "Step 1: Open MPC-BE.\n"
            "Step 2: Press 'O' on your keyboard, or go to: View → Options.\n"
            "Step 3: In the left sidebar, click on 'Player' → 'Web Interface'.\n"
            f"Step 4: Check the box: [✓] Listen on port (default is {MPC_PORT}).\n"
            "Step 5: Check the box: [✓] Allow access from localhost only (for security).\n"
            "Step 6: Click 'Apply', then click 'OK'. Done!\n\n"
            "Troubleshooting Tips:\n"
            "• If the tracker shows 'Not connected', ensure MPC-BE is running with a video file open.\n"
            "• Verify the port number matches the port configured in Player Settings."
        )
        ttk.Label(mpc_tab, text=mpc_instructions, justify="left", wraplength=680, font=("Segoe UI", 10)).pack(anchor="w", pady=(8, 16))

        mpc_btn_row = ttk.Frame(mpc_tab)
        mpc_btn_row.pack(fill="x")
        def test_mpc_in_guide():
            ok, msg = test_mpc_conn()
            (messagebox.showinfo if ok else messagebox.showwarning)("MPC-BE Test", msg, parent=window)
        ttk.Button(mpc_btn_row, text="Test MPC-BE Connection", command=test_mpc_in_guide).pack(side="left")

        vlc_tab = ttk.Frame(notebook, padding=16)
        notebook.add(vlc_tab, text="  VLC Media Player Setup  ")

        ttk.Label(vlc_tab, text="How to Configure VLC Media Player", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        vlc_instructions = (
            "VLC comes with an HTTP web interface that requires a one-time activation and password.\n\n"
            "Step 1: Open VLC Media Player.\n"
            "Step 2: Go to: Tools → Preferences (or press Ctrl + P).\n"
            "Step 3: Under 'Show settings' at the bottom-left corner, select 'All'.\n"
            "Step 4: In the left tree list, click: Interface → Main interfaces.\n"
            "Step 5: In the right pane, check the box: [✓] Web (this enables Lua HTTP).\n"
            "Step 6: In the left tree, expand 'Main interfaces' and click on 'Lua'.\n"
            "Step 7: Under 'Lua HTTP', find the 'Password' field and type a password (e.g. 'vlc').\n"
            f"Step 8: Notice the 'Lua HTTP port' (default is {VLC_PORT}).\n"
            "Step 9: Click 'Save' at the bottom right.\n"
            "Step 10: ⭐ CRITICAL: Close and RESTART VLC completely! ⭐\n"
            "        (VLC's web server will not start until VLC is restarted)\n"
            "Step 11: In this tracker's Player Settings, enter the same password you chose.\n\n"
            "Troubleshooting Tips:\n"
            "• 401 Unauthorized: The password entered in Tracker Settings does not match VLC's password.\n"
            "• Connection refused: You must restart VLC after enabling the Web interface."
        )
        ttk.Label(vlc_tab, text=vlc_instructions, justify="left", wraplength=680, font=("Segoe UI", 10)).pack(anchor="w", pady=(8, 16))

        vlc_btn_row = ttk.Frame(vlc_tab)
        vlc_btn_row.pack(fill="x")
        def test_vlc_in_guide():
            ok, msg = test_vlc_conn()
            (messagebox.showinfo if ok else messagebox.showwarning)("VLC Test", msg, parent=window)
        ttk.Button(vlc_btn_row, text="Test VLC Connection", command=test_vlc_in_guide).pack(side="left")

        dual_tab = ttk.Frame(notebook, padding=16)
        notebook.add(dual_tab, text="  Using Both Players  ")

        ttk.Label(dual_tab, text="Using Both MPC-BE and VLC", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        dual_instructions = (
            "The tracker is designed to let you use MPC-BE, VLC, or both interchangeably!\n\n"
            "• Seamless Progress Sync:\n"
            "  All progress (furthest position, time spent, study sessions, ratings, notes) is stored in\n"
            "  the video folder, so you can watch in MPC-BE today and continue in VLC tomorrow.\n\n"
            "• Smart Auto-Detect:\n"
            "  When set to 'Auto-detect', the tracker automatically follows whichever player is open.\n\n"
            "• What happens if BOTH players are running at once?\n"
            "  1. If only one player is actively playing, the tracker follows the playing one.\n"
            "  2. If one player is playing a video from your lecture folder and the other is playing\n"
            "     something else (like music or a film), the tracker tracks your lecture.\n"
            "  3. If both are playing lectures from your folder, it prioritizes your chosen preference\n"
            "     (Prioritize MPC-BE or Prioritize VLC in Player Settings)."
        )
        ttk.Label(dual_tab, text=dual_instructions, justify="left", wraplength=680, font=("Segoe UI", 10)).pack(anchor="w", pady=(8, 16))

        close_row = ttk.Frame(window)
        close_row.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(close_row, text="Close", command=window.destroy).pack(side="right")

        if initial_tab == "vlc":
            notebook.select(vlc_tab)
        elif initial_tab == "both":
            notebook.select(dual_tab)

    def short_name(self,name):
        return name if len(name)<=26 else name[:20]+"**"+name[-4:]

    def file_size(self,path):
        try:return path.stat().st_size
        except OSError:return 0

    def chart_data(self,metric):
        if metric in ("total","covered","remaining","overall"):
            values=[]
            for path in vids():
                record=self.data.get(str(path.resolve()),{}); duration=float(record.get("duration") or 0); covered=min(float(record.get("furthest") or 0),duration) if duration else 0
                value=duration if metric=="total" else covered if metric=="covered" else max(0,duration-covered) if metric=="remaining" else (covered/duration*100 if duration else 0)
                if value:values.append({"name":path.name,"label":self.short_name(path.name),"value":value,"duration":duration,"size":self.file_size(path)})
            return sorted(values,key=lambda item:item["name"].lower())
        if metric=="rating":
            counts={rating:0 for rating in [index/2 for index in range(1,11)]}
            for path in vids():
                rating=float(self.data.get(str(path.resolve()),{}).get("rating") or 0)
                rating=round(rating*2)/2
                if rating in counts:counts[rating]+=1
            return [{"name":f"{rating:g} star","label":f"{rating:g}","value":value} for rating,value in counts.items()]
        sessions=[session for session in self.data.get("_study_sessions",[]) if isinstance(session,dict)]
        if not sessions:
            grouped={}
            for segment in self.data.get("_sessions",[]):
                if not isinstance(segment,dict):continue
                name=segment.get("session_name") or "Legacy activity"
                item=grouped.setdefault(name,{"id":name,"started_at":segment.get("started_at",""),"total":0,"video_total":0})
                item["total"]+=float(segment.get("session_duration",segment.get("duration",0)) or 0)
                item["video_total"]+=float(segment.get("video_play_duration",segment.get("duration",0)) or 0)
            sessions=list(grouped.values())
        if self.session:sessions.append(self.session)
        return [{"name":session.get("id","Unknown"),"label":session.get("id","Unknown"),"value":float(session.get("total",0) or 0),"video":float(session.get("video_total",0) or 0),"date":str(session.get("started_at",""))[:10]} for session in sorted(sessions,key=lambda item:str(item.get("started_at","")))]

    def open_chart(self,metric):
        t = THEMES.get(self.current_theme, THEMES["amoled"])
        title="Time Spent by Session" if metric=="spent" else f"{metric.title()} chart"
        window=tk.Toplevel(self.root); window.title(title); window.geometry("850x560"); window.configure(bg=t["bg"])
        controls=ttk.Frame(window); controls.pack(fill="x",padx=10,pady=8)
        chart_type=tk.StringVar(value="pie")
        ttk.Label(controls,text="Chart:").pack(side="left")
        ttk.Radiobutton(controls,text="Pie",variable=chart_type,value="pie").pack(side="left",padx=5)
        ttk.Radiobutton(controls,text="Bar",variable=chart_type,value="bar").pack(side="left")
        canvas=tk.Canvas(window,background=t["card_bg"],highlightthickness=1,highlightbackground=t["border"])
        canvas.pack(fill="both",expand=True,padx=10,pady=(0,5))
        details=tk.StringVar(value="Hover a chart item for details")
        ttk.Label(window,textvariable=details,anchor="w",wraplength=820).pack(fill="x",padx=10,pady=8)
        items=self.chart_data(metric)
        colors=("#6366f1","#38bdf8","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6")

        def render(*_):
            canvas.delete("all"); canvas.tag_unbind("chart", "<Enter>"); canvas.tag_unbind("chart", "<Leave>")
            if not items:
                canvas.create_text(420,250,text="No data available",fill=t["muted"]); return
            if chart_type.get()=="pie":
                total=sum(item["value"] for item in items); start=-90; cx,cy,r=330,260,190
                for index,item in enumerate(items):
                    extent=item["value"]/total*360; tag=f"chart{index}"; canvas.create_arc(cx-r,cy-r,cx+r,cy+r,start=start,extent=extent,fill=colors[index%len(colors)],outline=t["card_bg"],tags=("chart",tag))
                    canvas.tag_bind(tag,"<Enter>",lambda e,current=item:self.chart_details(current,metric,details,total))
                    start+=extent
                canvas.create_text(650,80,text=title,fill=t["fg"],font=("Segoe UI",14,"bold"))
                for index,item in enumerate(items):
                    canvas.create_rectangle(540,110+index*24,555,125+index*24,fill=colors[index%len(colors)],outline="")
                    canvas.create_text(565,117+index*24,text=item["label"],anchor="w",fill=t["fg"])
            else:
                canvas.create_text(440,20,text=title,fill=t["fg"],font=("Segoe UI",14,"bold"))
                if metric=="rating":
                    maximum=max(item["value"] for item in items) or 1; left=75; bottom=450; chart_height=350; bar_width=48; spacing=70; total=sum(i["value"] for i in items)
                    for index,item in enumerate(items):
                        x=left+index*spacing; bar_height=item["value"]/maximum*chart_height; tag=f"chart{index}"
                        canvas.create_rectangle(x,bottom-bar_height,x+bar_width,bottom,fill=colors[index%len(colors)],outline=t["border"],tags=("chart",tag))
                        canvas.create_text(x+bar_width/2,bottom+15,text=item["label"],anchor="n",fill=t["fg"])
                        canvas.tag_bind(tag,"<Enter>",lambda e,current=item:self.chart_details(current,metric,details,total))
                    rated=[float(self.data.get(str(path.resolve()),{}).get("rating") or 0) for path in vids()]
                    rated=[value for value in rated if 1<=value<=5]
                    if rated:
                        average=sum(rated)/len(rated); x=left+(average-0.5)*spacing+bar_width/2
                        canvas.create_line(x,80,x,bottom,fill=t["accent"],width=3)
                        canvas.create_text(x,60,text=f"Avg {average:.1f}",fill=t["fg"],font=("Segoe UI",10,"bold"))
                else:
                    maximum=max(item["value"] for item in items) or 1; left=130; width=620; bar_height=max(18,min(36,360//len(items))); offset=max(40,(420-len(items)*bar_height)//2)
                    for index,item in enumerate(items):
                        y=offset+index*bar_height; bar_width=item["value"]/maximum*width; tag=f"chart{index}"
                        canvas.create_text(left-8,y+bar_height/2,text=item["label"],anchor="e",fill=t["fg"])
                        canvas.create_rectangle(left,y,left+bar_width,y+bar_height-4,fill=colors[index%len(colors)],outline=t["border"],tags=("chart",tag))
                        canvas.tag_bind(tag,"<Enter>",lambda e,current=item:self.chart_details(current,metric,details,sum(i["value"] for i in items)))
        chart_type.trace_add("write",render); canvas.bind("<Configure>",render); render()

    def chart_details(self,item,metric,details,total):
        share=item["value"]/total*100 if total else 0
        if metric=="rating":text=f"{item['name']}: {int(item['value'])} lecture(s)"
        elif metric in ("study","spent"):
            text=f"{item['name']} | Date: {item.get('date','')} | Session time: {fmt(item['value'])} | Video playing time: {fmt(item.get('video',0))} | Share: {share:.1f}%"
        elif metric=="overall":text=f"Filename: {item['name']} | Overall covered: {item['value']:.1f}% | Size: {self.size_text(item['size'])}"
        else:text=f"Filename: {item['name']} | {metric.title()}: {fmt(item['value'])} | Share: {share:.1f}% | Size: {self.size_text(item['size'])}"
        details.set(text)

    def size_text(self,size):
        units=("B","KB","MB","GB","TB"); value=float(size)
        for unit in units:
            if value<1024 or unit==units[-1]:return f"{value:.1f} {unit}" if unit!="B" else f"{int(value)} B"
            value/=1024

    def draw(self):
        total=covered=0; ratings=[]
        study_total=sum(float(s.get("session_duration",s.get("duration",0)) or 0) for s in self.data.get("_sessions",[]) if isinstance(s,dict))
        if self.session: study_total+=float(self.session.get("total") or 0)
        rows=[]
        hidden=set(self.data.get("_hidden", []))
        for p in self.visible_vids():
            key=str(p.resolve())
            if key in hidden: continue
            r=self.data[key]; d=float(r.get("duration") or 0); f=float(r.get("furthest") or 0)
            if d:f=min(f,d)
            total+=d; covered+=f
            status="✓ Watched" if d and f>=d-2 else ("◐ In progress" if f>0 else "○ Not watched")
            rating=float(r.get("rating") or 0)
            if 1<=rating<=5: ratings.append(rating)
            spent=sum(float(s.get("session_duration",s.get("duration",0)) or 0) for s in self.data.get("_sessions",[]) if isinstance(s,dict) and str(s.get("lecture","")).lower()==p.name.lower())
            rows.append((p, status, d, f, rating, str(r.get("review") or ""), spent))
        sort_index={"lecture":0,"status":1,"covered":3,"duration":2,"progress":3,"rating":4,"review":5,"spent":6}[self.sort_column]
        if self.sort_column=="lecture":
            rows.sort(key=lambda row: row[0].name.lower(), reverse=self.sort_reverse)
        elif self.sort_column=="status":
            rows.sort(key=lambda row: row[1].lower(), reverse=self.sort_reverse)
        elif self.sort_column=="review":
            rows.sort(key=lambda row: row[5].lower(), reverse=self.sort_reverse)
        else:
            rows.sort(key=lambda row: row[sort_index], reverse=self.sort_reverse)

        existing_iids = list(self.tree.get_children())
        new_iids = [str(p.resolve()) for p, *_ in rows]
        if existing_iids == new_iids:
            for p, status, d, f, rating, review, spent in rows:
                iid = str(p.resolve())
                checkbox = "☑" if iid in self.checked else "☐"
                if not self.select_mode: checkbox = ""
                rating_text = f"{rating:g}/5" if 1 <= rating <= 5 else "—"
                tag = "watched" if d and f >= d - 2 else ("progress" if f > 0 else "unwatched")
                new_vals = (checkbox, p.name, status, fmt(f), fmt(d) if d else "Unknown", f"{f/d*100:.1f}%" if d else "—", rating_text, review, fmt(spent))
                if tuple(self.tree.item(iid, "values")) != new_vals:
                    self.tree.item(iid, values=new_vals, tags=(tag,))
        else:
            self.tree.delete(*existing_iids)
            for p, status, d, f, rating, review, spent in rows:
                iid = str(p.resolve())
                checkbox = "☑" if iid in self.checked else "☐"
                if not self.select_mode: checkbox = ""
                rating_text = f"{rating:g}/5" if 1 <= rating <= 5 else "—"
                tag = "watched" if d and f >= d - 2 else ("progress" if f > 0 else "unwatched")
                self.tree.insert("", "end", iid=iid, values=(checkbox, p.name, status, fmt(f), fmt(d) if d else "Unknown", f"{f/d*100:.1f}%" if d else "—", rating_text, review, fmt(spent)), tags=(tag,))

        pct=covered/total*100 if total else 0
        self.vars[0].set("Total: "+big(total)); self.vars[1].set("Covered: "+big(covered))
        self.vars[2].set("Remaining: "+big(max(0,total-covered))); self.vars[3].set(f"Overall: {pct:.1f}%")
        self.vars[4].set(f"Avg rating: {sum(ratings)/len(ratings):.1f}/5" if ratings else "Avg rating: —")
        self.vars[5].set("Study time: "+big(study_total))
        self.pb["value"]=pct
        self.selected_count.set(f"{len(self.checked)} selected" if self.select_mode else "")
        self.draw_activity()

    def draw_activity(self):
        if hasattr(self, "activity_frame") and not self.activity_frame.winfo_ismapped():
            return
        sessions=[]
        grouped_keys=set()
        for study_session in self.data.get("_study_sessions",[]):
            if not isinstance(study_session,dict):continue
            session_name=study_session.get("id", "Unknown")
            for segment in study_session.get("segments",[]):
                if not isinstance(segment,dict):continue
                item=dict(segment); item["session_name"]=session_name
                grouped_keys.add((item.get("lecture"),item.get("started_at")))
                sessions.append(item)
        for segment in self.data.get("_sessions",[]):
            if not isinstance(segment,dict):continue
            key=(segment.get("lecture"),segment.get("started_at"))
            if key not in grouped_keys:
                item=dict(segment); item["session_name"]=item.get("session_name") or "Legacy activity"
                sessions.append(item)
        if self.active_segment:
            sessions.append({"session_name":self.session.get("id","") if self.session else "","lecture":self.active_segment["lecture"],"started_at":self.active_segment["started_at"],"session_duration":self.active_segment["session_elapsed"],"video_play_duration":self.active_segment["video_elapsed"]})
        if self.activity_filter!="all":
            sessions=[s for s in sessions if isinstance(s,dict) and s.get("session_name")==self.activity_filter]
        sort_column={"session_name":"session_name","lecture":"lecture","started":"started_at"}.get(self.activity_sort_column)
        if sort_column:
            sessions.sort(key=lambda s:str(s.get(sort_column," ")).lower(),reverse=self.activity_sort_reverse)
        elif self.activity_sort_column=="session":
            sessions.sort(key=lambda s:float(s.get("session_duration",s.get("duration",0)) or 0),reverse=self.activity_sort_reverse)
        else:
            sessions.sort(key=lambda s:float(s.get("video_play_duration",s.get("duration",0)) or 0),reverse=self.activity_sort_reverse)
        session_total=sum(float(s.get("session_duration",s.get("duration",0)) or 0) for s in sessions if isinstance(s,dict))
        video_total=sum(float(s.get("video_play_duration",s.get("duration",0)) or 0) for s in sessions if isinstance(s,dict))
        self.session_total_text.set("Session total: "+fmt(session_total)); self.video_total_text.set("Video playing total: "+fmt(video_total))

        existing_items = list(self.activity_tree.get_children())
        valid_sessions = [s for s in sessions if isinstance(s, dict)]
        if len(existing_items) == len(valid_sessions):
            for iid, segment in zip(existing_items, valid_sessions):
                started = str(segment.get("started_at", ""))
                vals = (segment.get("session_name", ""), segment.get("lecture", ""), started.replace("T", " "), fmt(segment.get("session_duration", segment.get("duration", 0))), fmt(segment.get("video_play_duration", segment.get("duration", 0))))
                if tuple(self.activity_tree.item(iid, "values")) != vals:
                    self.activity_tree.item(iid, values=vals)
        else:
            self.activity_tree.delete(*existing_items)
            for segment in valid_sessions:
                started = str(segment.get("started_at", ""))
                self.activity_tree.insert("", "end", values=(segment.get("session_name", ""), segment.get("lecture", ""), started.replace("T", " "), fmt(segment.get("session_duration", segment.get("duration", 0))), fmt(segment.get("video_play_duration", segment.get("duration", 0)))))

    def sort_activity(self,column):
        if self.activity_sort_column==column:
            self.activity_sort_reverse=not self.activity_sort_reverse
        else:
            self.activity_sort_column=column; self.activity_sort_reverse=False
        self.draw_activity()

    def show_current_activity(self):
        self.activity_filter=self.session.get("id","") if self.session else "__none__"
        self.draw_activity()

    def show_all_activity(self):
        self.activity_filter="all"
        self.draw_activity()

    def refresh_activity_menu(self):
        self.other_session_menu.delete(0,tk.END)
        sessions=[s for s in self.data.get("_study_sessions",[]) if isinstance(s,dict)]
        if self.session:
            sessions=[dict(self.session,ended_at="",_active=True)]+sessions
        if any(isinstance(segment,dict) and not segment.get("session_name") for segment in self.data.get("_sessions",[])):
            sessions.append({"id":"Legacy activity","started_at":"0000-00-00T00:00:00"})
        sessions.sort(key=lambda s:str(s.get("started_at", "")),reverse=True)
        if not sessions:
            self.other_session_menu.add_command(label="No saved sessions",state="disabled")
            return
        for session in sessions:
            started=str(session.get("started_at", "")); session_id=session.get("id","Unknown")
            label=f"{session_id} | {started.replace('T',' ')}"
            self.other_session_menu.add_command(label=label,command=lambda value=session_id:self.show_activity_session(value))

    def show_activity_session(self,session_id):
        self.activity_filter=session_id
        self.draw_activity()

    def update_scrollregion(self, event=None):
        try:
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        except Exception:
            pass

    def hide_activity(self):
        self.activity_frame.pack_forget()
        self.show_activity_button.pack(fill="x",padx=14,pady=(0,10),before=self.body_frame)
        self.root.after_idle(self.update_scrollregion)

    def show_activity(self):
        self.show_activity_button.pack_forget()
        self.activity_frame.pack(fill="x",padx=14,pady=(0,10),before=self.body_frame)
        self.root.after_idle(self.update_scrollregion)

    def add_manual_segment(self):
        lecture=simpledialog.askstring("Manual segment","Lecture file name:",parent=self.root)
        if not lecture:return
        session=simpledialog.askstring("Manual segment","Session time (MM:SS or H:MM:SS):",parent=self.root)
        if not session:return
        video=simpledialog.askstring("Manual segment","Video playing time (MM:SS or H:MM:SS):",parent=self.root)
        if video is None:return
        def seconds(value):
            parts=[int(part) for part in value.split(":")]
            return parts[0]*3600+parts[1]*60+parts[2] if len(parts)==3 else parts[0]*60+parts[1]
        try:session_seconds=seconds(session); video_seconds=seconds(video)
        except (ValueError,IndexError):
            messagebox.showerror("Invalid time","Use MM:SS or H:MM:SS.",parent=self.root); return
        self.data.setdefault("_sessions",[]).append({"lecture":lecture,"started_at":datetime.now().isoformat(timespec="seconds"),"ended_at":datetime.now().isoformat(timespec="seconds"),"session_duration":session_seconds,"video_play_duration":video_seconds,"duration":session_seconds,"manual":True})
        save(self.data); self.draw()

    def sort_tree(self,column):
        if column=="select": return
        if self.sort_column==column:
            self.sort_reverse=not self.sort_reverse
        else:
            self.sort_column=column; self.sort_reverse=False
        self.draw()

    def tree_click(self,e):
        iid=self.tree.identify_row(e.y)
        if not iid:return
        column=self.tree.identify_column(e.x)
        if not self.select_mode or column!="#1": return
        if iid in self.checked: self.checked.remove(iid)
        else: self.checked.add(iid)
        self.draw()
        return "break"

    def open_lecture(self,e):
        column=self.tree.identify_column(e.x)
        iid=self.tree.identify_row(e.y)
        if not iid:return
        p=Path(iid)
        if column=="#2": os.startfile(iid)
        elif column=="#7": self.edit_rating(p,e)
        elif column=="#8": self.edit_review(p,e)
        elif column=="#9": self.open_chart("spent")

    def selected(self):
        s=self.tree.selection()
        return Path(s[0]) if s else None

    def menu(self,e):
        iid=self.tree.identify_row(e.y)
        if not iid:return
        self.tree.selection_set(iid)
        p=Path(iid)
        bulk=self.select_mode and str(p.resolve()) in self.checked
        t=THEMES.get(self.current_theme,THEMES["amoled"])
        m=tk.Menu(self.root,tearoff=0,bg=t["card_bg"],fg=t["fg"],activebackground=t["accent"],activeforeground=t["accent_text"],relief="solid",bd=1)
        m.add_command(label="Unselect" if bulk else "Select",command=lambda: self.toggle_select(p))
        m.add_separator()
        m.add_command(label="✓ Mark all selected as watched" if bulk else "✓ Mark as watched",command=lambda: self.context_watched(p,True))
        m.add_command(label="○ Mark all selected as not watched" if bulk else "○ Mark as not watched",command=lambda: self.context_watched(p,False))
        m.add_command(label="Set covered time for all selected..." if bulk else "Set covered time...",command=lambda: self.context_settime(p))
        m.add_command(label="Set all selected to current player position" if bulk else "Set to current player position",command=lambda: self.context_set_current(p))
        m.add_command(label="Set rating and review for all selected..." if bulk else "Set rating and review...",command=lambda: self.context_rating_review(p))
        m.add_separator()

        # Lecture row actions
        if not bulk:
            rec = self.data.get(str(p.resolve()), {})
            dur = int(rec.get("duration", 0))
            if dur > 0:
                m.add_command(label=f"🔔 Set Reminder to Duration ({fmt(dur)})",
                              command=lambda: self._set_reminder_to_lecture_duration(p))
            m.add_command(label="▶ Start Study Session for this Lecture",
                          command=lambda: self._start_session_for_lecture(p))
            m.add_command(label="📂 Show in File Explorer",
                          command=lambda: self._open_in_explorer(p))
            copy_menu = tk.Menu(m, tearoff=0, bg=t["card_bg"], fg=t["fg"],
                                activebackground=t["accent"], activeforeground=t["accent_text"])
            copy_menu.add_command(label="Lecture Title", command=lambda: self._copy_to_clipboard(p.name))
            copy_menu.add_command(label="File Path", command=lambda: self._copy_to_clipboard(str(p.resolve())))
            m.add_cascade(label="📋 Copy", menu=copy_menu)
        else:
            m.add_command(label="📂 Show in File Explorer",
                          command=lambda: self._open_in_explorer(p))
            m.add_command(label="📋 Copy Selected Titles",
                          command=lambda: self._copy_to_clipboard("\n".join(x.name for x in self.selected_paths())))

        m.add_separator()
        if self.select_mode and str(p.resolve()) in self.checked:
            m.add_command(label="Remove all selected",command=lambda: self.remove_selected())
        else:
            m.add_command(label="Remove from tracker",command=lambda: self.context_remove(p))
        try:
            m.tk_popup(e.x_root,e.y_root)
        finally:
            m.grab_release()

    def _set_reminder_to_lecture_duration(self, p):
        """Set reminder countdown to the duration of this lecture."""
        rec = self.data.get(str(p.resolve()), {})
        dur = int(rec.get("duration", 0))
        if dur > 0:
            self._set_live_countdown_direct(dur)
        else:
            messagebox.showinfo("Duration unavailable",
                                "This lecture does not have duration information yet.",
                                parent=self.root)

    def _start_session_for_lecture(self, p):
        """Start or focus study session on this specific lecture."""
        if not self.session:
            self.start_session()
        elif self.session.get("status") == "paused":
            self.start_session()
        now = time.monotonic()
        key = str(p.resolve())
        if self.active_segment:
            self.finish_segment()
        self.active_segment = {
            "lecture": p.name,
            "path": key,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "session_elapsed": 0,
            "video_elapsed": 0,
            "last_tick": now
        }
        self.timer_lecture_full = p.name
        self.timer_lecture.set(self._truncate_lecture(p.name))
        self.update_session_display()

    def _open_in_explorer(self, p):
        """Reveal file in File Explorer."""
        try:
            target = str(p.resolve())
            if os.name == "nt":
                subprocess.Popen(["explorer.exe", f"/select,{target}"])
            else:
                subprocess.Popen(["open", "-R", target])
        except Exception as err:
            messagebox.showerror("Error", f"Could not reveal file: {err}", parent=self.root)

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except Exception:
            pass

    def enable_select(self,p=None):
        self.select_mode=True
        if p: self.checked.add(str(p.resolve()))
        self.tree.column("select",width=55,stretch=False)
        self.select_all_button.pack(side="left",padx=7)
        self.unselect_all_button.pack(side="left",padx=7)
        self.done_selecting_button.pack(side="left",padx=7)
        self.selected_count_label.pack(side="left",padx=7)
        self.draw()

    def toggle_select(self,p):
        key=str(p.resolve())
        if self.select_mode and key in self.checked:
            self.checked.remove(key)
            self.draw()
        else:
            self.enable_select(p)

    def select_all(self):
        self.checked={str(p.resolve()) for p in self.visible_vids() if str(p.resolve()) not in set(self.data.get("_hidden", []))}
        self.draw()

    def unselect_all(self):
        self.checked.clear()
        self.draw()

    def selected_paths(self):
        return [Path(key) for key in self.checked if self.tree.exists(key)]

    def context_paths(self,p):
        if self.select_mode and str(p.resolve()) in self.checked:
            return self.selected_paths()
        return [p]

    def context_watched(self,p,watched):
        paths=self.context_paths(p)
        if len(paths)==1:
            (self.watched if watched else self.unwatched)(paths[0])
        else:
            self.mark_selected(watched)

    def context_remove(self,p):
        paths=self.context_paths(p)
        if len(paths)==1:
            self.remove_from_tracker(paths[0])
        else:
            self.remove_selected()

    def context_settime(self,p):
        paths=self.context_paths(p)
        if len(paths)==1:
            self.settime(paths[0])
            return
        x=simpledialog.askstring("Set covered time",f"Enter the covered time for {len(paths)} selected lectures:\n\nExamples: 1:23:45 or 83:45")
        if not x:return
        try:
            parts=[int(z) for z in x.split(":")]
            sec=parts[0]*3600+parts[1]*60+parts[2] if len(parts)==3 else parts[0]*60+parts[1]
            if sec<0:raise ValueError
        except (ValueError,IndexError):
            messagebox.showerror("Invalid time","Use MM:SS or H:MM:SS.")
            return
        for selected in paths:
            r=self.data[str(selected.resolve())]; d=r.get("duration") or 0
            r["furthest"]=max(0,min(sec,d)) if d else sec; r["manual"]=True
        save(self.data); self.draw()

    def context_set_current(self,p):
        paths=self.context_paths(p); info=self.current_info or getattr(self, "_latest_player_info", None) or poll_player()
        if not info:return
        for selected in paths:
            r=self.data[str(selected.resolve())]
            r["furthest"]=max(r.get("furthest",0),info["pos"])
            if info["dur"]:r["duration"]=info["dur"]
            r["manual"]=True
        save(self.data); self.draw()

    def find_current_lecture(self,info):
        if not info or not info.get("path"): return None
        current=Path(info["path"])
        for video in vids():
            if video.resolve()==current.resolve() or video.name.lower()==current.name.lower(): return video
        return None

    def is_playing(self,info):
        return bool(info and str(info.get("state","")).lower() in {"playing","play","running"})

    def save_auto_start(self):
        self.data.setdefault("_settings",{})["auto_start"]=self.auto_start.get()
        save(self.data)

    def update_session_display(self):
        total=self.session.get("total",0) if self.session else 0
        self.timer_text.set(fmt(total))
        if self.session and self.active_segment:
            self.timer_lecture.set(f"{self.session['id']} • {self.active_segment['lecture']}")
        elif self.session:
            self.timer_lecture.set(f"{self.session['id']} • Waiting for recognized lecture")
        elif not self.session:
            self.timer_lecture.set("Waiting for media player activity")
        self.start_session_button.configure(text="Resume Session" if self.session and self.session["status"]=="paused" else "Start Session")
        self.start_session_button.configure(state="disabled" if self.session and self.session["status"]=="active" else "normal")
        self.pause_session_button.configure(state="normal" if self.session and self.session["status"]=="active" else "disabled")
        self.stop_session_button.configure(state="normal" if self.session else "disabled")

    def finish_segment(self):
        if not self.active_segment:return
        segment=self.active_segment
        if segment["session_elapsed"]>0:
            segment_record={
                "session_name":self.session.get("id","") if self.session else "",
                "lecture":segment["lecture"],"started_at":segment["started_at"],
                "ended_at":datetime.now().isoformat(timespec="seconds"),
                "session_duration":round(segment["session_elapsed"]),
                "video_play_duration":round(segment["video_elapsed"]),
                "duration":round(segment["session_elapsed"])
            }
            if self.session:
                self.session.setdefault("segments",[]).append(segment_record)
                self.session["video_total"]+=segment_record["video_play_duration"]
            self.data.setdefault("_sessions",[]).append(segment_record)
        self.active_segment=None

    def track_activity(self,info,lecture):
        now=time.monotonic()
        playing=self.is_playing(info)
        if not self.session or self.session["status"]!="active" or not lecture:
            if self.active_segment:self.finish_segment()
            return
        key=str(lecture.resolve())
        if not self.active_segment or self.active_segment["lecture"]!=lecture.name:
            if self.active_segment:self.finish_segment()
            self.active_segment={"lecture":lecture.name,"path":key,"started_at":datetime.now().isoformat(timespec="seconds"),"session_elapsed":0,"video_elapsed":0,"last_tick":now}
        else:
            delta=max(0,now-self.active_segment["last_tick"])
            self.active_segment["session_elapsed"]+=delta; self.session["total"]+=delta
            if playing:self.active_segment["video_elapsed"]+=delta
            self.active_segment["last_tick"]=now
        self.update_session_display()

    def start_session(self):
        if self.session and self.session["status"]=="paused":
            self._reminder_elapsed = 0  # reset countdown on resume
            self._auto_paused_session = False
            self.session["status"]="active"; self.session["resumed_at"]=datetime.now().isoformat(timespec="seconds"); self.update_session_display(); return
        if self.session:return
        counter=int(self.data.get("_session_counter",0) or 0)+1
        self.data["_session_counter"]=counter
        self._auto_paused_session = False
        self.session={"id":f"Session{counter:04d}","status":"active","started_at":datetime.now().isoformat(timespec="seconds"),"total":0,"video_total":0,"segments":[]}
        save(self.data)
        self._reminder_elapsed = 0  # reset countdown on new session
        self.auto_block_path=None; self.update_session_display()

    def pause_session(self):
        if not self.session:return
        self.sound_engine.stop()          # stop reminder sound on pause
        self._reminder_elapsed = 0        # reset countdown
        if not getattr(self, "_auto_paused_session", False):
            self._auto_paused_session = False
        self.track_activity(self.current_info,self.find_current_lecture(self.current_info)); self.finish_segment(); self.session["status"]="paused"; self.update_session_display(); save(self.data)

    def stop_session(self,save_session=True):
        if not self.session:return
        self.sound_engine.stop()          # stop reminder sound on session end
        self._reminder_elapsed = 0        # reset countdown
        self.track_activity(self.current_info,self.find_current_lecture(self.current_info)); self.finish_segment()
        if save_session:
            completed=dict(self.session); completed["ended_at"]=datetime.now().isoformat(timespec="seconds")
            completed.pop("status",None); completed.pop("segments",None)
            completed["segments"]=self.session.get("segments",[])
            self.data.setdefault("_study_sessions",[]).append(completed); save(self.data)
        if self.current_info:self.auto_block_path=self.current_info.get("path")
        self.timer_lecture_full = ""
        self.session=None; self.active_segment=None; self.timer_text.set("00:00:00"); self.timer_lecture.set("Waiting for media player activity"); self.update_session_display(); self.draw()


    def close(self):
        self._poller_active = False
        self.stop_session(save_session=True)
        self.sound_engine.stop()          # ensure audio thread is cleaned up
        try:
            self.root.destroy()
        except Exception:
            pass

    def show_sessions(self):
        sessions=[s for s in self.data.get("_study_sessions",[]) if isinstance(s,dict)]
        sessions.sort(key=lambda s:str(s.get("started_at", "")),reverse=True)
        window=tk.Toplevel(self.root); window.title("Study session history"); window.geometry("850x380"); window.transient(self.root)
        cols=("session","date","started","ended","lectures","duration"); tree=ttk.Treeview(window,columns=cols,show="headings")
        for c,t,w in zip(cols,("Session","Date","Started","Stopped","Lectures","Duration"),(110,100,150,150,100,100)):
            tree.heading(c,text=t); tree.column(c,width=w,anchor="w" if c=="session" else "center")
        for session in reversed(sessions):
            started=str(session.get("started_at", "")); segments=session.get("segments",[])
            lectures=len({s.get("lecture") for s in segments if isinstance(s,dict)})
            duration=session.get("total",session.get("total_session_time",0))
            tree.insert("","end",values=(session.get("id",""),started[:10],started[11:19],str(session.get("ended_at",""))[11:19],lectures,fmt(duration)))
        tree.pack(fill="both",expand=True,padx=10,pady=10)

    def _show_stopwatch_context_menu(self, event):
        """Right-click on stopwatch time badge: session adjustment & controls."""
        menu = tk.Menu(self.root, tearoff=0, bg="#161b22", fg="#e6edf3",
                       activebackground="#1f6feb", activeforeground="#ffffff",
                       relief="solid", bd=1)

        has_session = bool(self.session)
        is_active = bool(self.session and self.session.get("status") == "active")

        # Session adjustments (+15m, +5m, +1m, -1m, -5m, -15m)
        adjust_menu = tk.Menu(menu, tearoff=0, bg="#161b22", fg="#e6edf3",
                              activebackground="#1f6feb", activeforeground="#ffffff")
        deltas = [
            ("+15 min", 900),
            ("+5 min", 300),
            ("+1 min", 60),
            ("-1 min", -60),
            ("-5 min", -300),
            ("-15 min", -900),
        ]
        for lbl, d in deltas:
            adjust_menu.add_command(
                label=lbl,
                command=lambda delta=d: self._adjust_session_time(delta),
                state="normal" if has_session else "disabled"
            )
        menu.add_cascade(label="⏱ Adjust Session Time", menu=adjust_menu)

        # Quick session controls
        if not has_session:
            menu.add_command(label="▶ Start Study Session", command=self.start_session)
        elif is_active:
            menu.add_command(label="⏸ Pause Session", command=self.pause_session)
            menu.add_command(label="⏹ End Session", command=self.stop_session)
        else:
            menu.add_command(label="▶ Resume Session", command=self.start_session)
            menu.add_command(label="⏹ End Session", command=self.stop_session)

        menu.add_separator()

        # Toggle Auto-pause with video
        auto_pause = self.auto_pause_on_video.get()
        prefix = "✓ " if auto_pause else "   "
        menu.add_command(
            label=f"{prefix}Auto-pause when Video Pauses",
            command=self._toggle_auto_pause_video
        )

        # Copy Session Duration
        menu.add_command(
            label="📋 Copy Session Duration",
            command=self._copy_session_duration
        )

        # View History
        menu.add_command(label="📜 Study Session History...", command=self.show_sessions)

        menu.tk_popup(event.x_root, event.y_root)

    def _adjust_session_time(self, delta_s):
        """Add or subtract seconds from the current session's elapsed time."""
        if not self.session:
            return
        cur_total = float(self.session.get("total", 0))
        new_total = max(0.0, cur_total + delta_s)
        self.session["total"] = new_total
        if self.active_segment:
            cur_seg = float(self.active_segment.get("session_elapsed", 0))
            self.active_segment["session_elapsed"] = max(0.0, cur_seg + delta_s)
        save(self.data)
        self.update_session_display()

    def _toggle_auto_pause_video(self):
        """Toggle auto-pause session on media player pause."""
        cur = self.auto_pause_on_video.get()
        self.auto_pause_on_video.set(not cur)
        self.data.setdefault("_settings", {})["auto_pause_on_video"] = self.auto_pause_on_video.get()
        save(self.data)

    def _copy_session_duration(self):
        """Copy current session duration to clipboard."""
        cur = self.timer_text.get()
        self.root.clipboard_clear()
        self.root.clipboard_append(cur)

    def edit_rating(self,p,event=None):
        record=self.data[str(p.resolve())]
        bbox=self.tree.bbox(str(p.resolve()),column="#7")
        if not bbox:return
        rating=tk.StringVar(value=str(record.get("rating") or ""))
        editor=tk.Entry(self.tree,textvariable=rating,justify="center")
        editor.place(x=bbox[0],y=bbox[1],width=bbox[2],height=bbox[3])
        editor.focus_set(); editor.select_range(0,tk.END)

        def adjust_rating(event):
            try:value=float(rating.get() or 0)
            except ValueError:value=0
            step=0.5 if event.delta>0 else -0.5
            rating.set(str(max(0,min(5,round(value+step,1)))))
            return "break"

        def save_rating(event=None):
            try:value=float(rating.get().strip() or 0)
            except ValueError:value=-1
            if value and (not 1<=value<=5 or abs(value*2-round(value*2))>1e-9):
                messagebox.showerror("Invalid rating","Choose a rating from 1 to 5, or 0 to clear it.",parent=self.root)
                editor.focus_set(); return "break"
            record["rating"]=round(value,1); save(self.data); editor.destroy(); self.draw()

        def cancel_rating(event=None):
            editor.destroy(); self.draw(); return "break"

        editor.bind("<MouseWheel>",adjust_rating)
        editor.bind("<Return>",save_rating)
        editor.bind("<FocusOut>",save_rating)
        editor.bind("<Escape>",cancel_rating)

    def edit_review(self,p,event=None):
        record=self.data[str(p.resolve())]
        window=tk.Toplevel(self.root); window.title("Review lecture"); window.geometry("520x300")
        window.transient(self.root); window.grab_set()
        ttk.Label(window,text=p.name).pack(anchor="w",padx=14,pady=(14,6))
        editor=tk.Text(window,height=9,wrap="word")
        editor.pack(fill="both",expand=True,padx=14,pady=6)
        editor.insert("1.0",str(record.get("review") or "")); editor.focus_set()
        self.position_popup(window,event)

        def save_review():
            record["review"]=editor.get("1.0",tk.END).strip()
            save(self.data); self.draw(); window.destroy()

        buttons=ttk.Frame(window); buttons.pack(fill="x",padx=14,pady=14)
        ttk.Button(buttons,text="Save",command=save_review).pack(side="left")
        ttk.Button(buttons,text="Cancel",command=window.destroy).pack(side="right")

    def position_popup(self,window,event):
        if event:
            x=self.root.winfo_rootx()+event.x+12
            y=self.root.winfo_rooty()+event.y+12
            window.geometry(f"+{x}+{y}")

    def context_rating_review(self,p):
        paths=self.context_paths(p)
        current=self.data[str(paths[0].resolve())] if len(paths)==1 else {}
        value=simpledialog.askstring(
            "Rating",
            "Enter a rating from 1 to 5 (blank or 0 clears it):",
            initialvalue=str(current.get("rating") or "") if len(paths)==1 else "",
            parent=self.root
        )
        if value is None:return
        try:
            rating=float(value.strip()) if value.strip() else 0
            if rating!=0 and (not 1<=rating<=5 or abs(rating*2-round(rating*2))>1e-9):raise ValueError
        except ValueError:
            messagebox.showerror("Invalid rating","Enter a number from 1 to 5, or 0 to clear the rating.")
            return
        review=simpledialog.askstring(
            "Review",
            "Enter a review:",
            initialvalue=str(current.get("review") or "") if len(paths)==1 else "",
            parent=self.root
        )
        if review is None:return
        for selected in paths:
            record=self.data[str(selected.resolve())]
            record["rating"]=rating; record["review"]=review.strip()
        save(self.data); self.draw()

    def mark_selected(self,watched):
        paths=self.selected_paths()
        if not paths:return
        for p in paths:
            r=self.data[str(p.resolve())]
            if watched:
                d=r.get("duration") or duration_ffprobe(p)
                if not d:
                    messagebox.showerror("Duration unavailable",f"Could not detect the duration of:\n\n{p.name}")
                    continue
                r["duration"]=d; r["furthest"]=d
            else:
                r["furthest"]=0
            r["manual"]=True
        save(self.data); self.draw()

    def remove_selected(self):
        paths=self.selected_paths()
        if not paths:return
        if not messagebox.askyesno("Remove selected",f"Remove {len(paths)} lecture(s) from the tracker?\n\nThe video files will not be deleted."):
            return
        hidden=self.data.setdefault("_hidden", [])
        for p in paths:
            key=str(p.resolve())
            if key not in hidden:hidden.append(key)
        save(self.data)
        self.exit_select_mode()

    def exit_select_mode(self):
        self.select_mode=False; self.checked.clear()
        for button in (self.select_all_button,self.unselect_all_button,self.done_selecting_button):
            button.pack_forget()
        self.selected_count_label.pack_forget()
        self.tree.column("select",width=0,stretch=False)
        self.draw()

    def export_progress(self):
        target=filedialog.asksaveasfilename(
            parent=self.root,title="Export lecture progress",defaultextension=".json",
            filetypes=[("JSON files","*.json"),("All files","*.*")],initialfile="lecture_progress.json"
        )
        if not target:return
        progress={}
        for p in vids():
            key=str(p.resolve())
            if key in self.data:progress[p.name]=self.data[key]
        payload={"progress":progress,"hidden":[Path(key).name for key in self.data.get("_hidden", [])],
               "settings":self.data.get("_settings",{}),"sessions":self.data.get("_sessions",[]),
               "study_sessions":self.data.get("_study_sessions",[]),"session_counter":self.data.get("_session_counter",0)}
        try:
            Path(target).write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
            messagebox.showinfo("Export complete",f"Exported progress for {len(progress)} lecture(s).")
        except OSError as error:
            messagebox.showerror("Export failed",str(error))

    def import_progress(self):
        source=filedialog.askopenfilename(
            parent=self.root,title="Import lecture progress",
            filetypes=[("JSON files","*.json"),("All files","*.*")]
        )
        if not source:return
        try:
            imported=json.loads(Path(source).read_text(encoding="utf-8"))
            if not isinstance(imported,dict):raise ValueError("The file must contain a JSON object.")
        except (OSError,ValueError,json.JSONDecodeError) as error:
            messagebox.showerror("Import failed",str(error)); return
        progress=imported.get("progress",imported)
        current={p.name.lower():str(p.resolve()) for p in vids()}
        count=0
        for name,record in progress.items():
            key=current.get(str(name).lower())
            if key and isinstance(record,dict):self.data[key]=record; count+=1
        hidden_names={str(name).lower() for name in imported.get("hidden",[]) if isinstance(name,str)}
        hidden=self.data.setdefault("_hidden",[])
        for name,key in current.items():
            if name in hidden_names and key not in hidden:hidden.append(key)
        if isinstance(imported.get("settings"),dict):
            self.data["_settings"]=imported["settings"]
            self.load_settings()
        if isinstance(imported.get("sessions"),list):
            existing=self.data.setdefault("_sessions",[])
            known={(s.get("lecture"),s.get("started_at")) for s in existing if isinstance(s,dict)}
            for session in imported["sessions"]:
                if isinstance(session,dict) and (session.get("lecture"),session.get("started_at")) not in known:
                    existing.append(session)
        if isinstance(imported.get("study_sessions"),list):
            existing=self.data.setdefault("_study_sessions",[])
            known={s.get("id") for s in existing if isinstance(s,dict)}
            for session in imported["study_sessions"]:
                if isinstance(session,dict) and session.get("id") not in known:existing.append(session)
        self.data["_session_counter"]=max(int(self.data.get("_session_counter",0) or 0),int(imported.get("session_counter",0) or 0))
        save(self.data); self.refresh()
        messagebox.showinfo("Import complete",f"Imported progress for {count} matching lecture(s).")

    def watched(self,p=None):
        p=p or self.selected()
        if not p:return
        r=self.data[str(p.resolve())]; d=r.get("duration") or duration_ffprobe(p)
        if not d:
            messagebox.showerror(
                "Duration unavailable",
                "The lecture duration could not be detected, so it cannot be marked as watched."
            )
            return
        r["duration"]=d
        r["furthest"]=d
        r["manual"]=True
        save(self.data); self.draw()

    def unwatched(self,p=None):
        p=p or self.selected()
        if p:
            r=self.data[str(p.resolve())]; r["furthest"]=0;r["manual"]=True;save(self.data);self.draw()

    def settime(self,p=None):
        p=p or self.selected()
        if not p:return
        r=self.data[str(p.resolve())]; d=r.get("duration") or 0
        x=simpledialog.askstring("Set covered time",f"Enter time for:\n{p.name}\n\nExamples: 1:23:45 or 83:45")
        if not x:return
        try:
            parts=[int(z) for z in x.split(":")]
            sec=parts[0]*3600+parts[1]*60+parts[2] if len(parts)==3 else parts[0]*60+parts[1]
            r["furthest"]=max(0,min(sec,d)) if d else max(0,sec); r["manual"]=True;save(self.data);self.draw()
        except: messagebox.showerror("Invalid time","Use MM:SS or H:MM:SS.")

    def set_current(self,p=None):
        p=p or self.selected(); info=self.current_info or getattr(self, "_latest_player_info", None) or poll_player()
        if not p or not info:return
        r=self.data[str(p.resolve())]; r["furthest"]=max(r.get("furthest",0),info["pos"])
        if info["dur"]:r["duration"]=info["dur"]
        r["manual"]=True;save(self.data);self.draw()

    def remove_from_tracker(self,p=None):
        p=p or self.selected()
        if not p:return
        if not messagebox.askyesno(
            "Remove from tracker",
            f"Remove this lecture from the tracker?\n\n{p.name}\n\nThe video file will not be deleted."
        ): return
        key=str(p.resolve())
        hidden=self.data.setdefault("_hidden", [])
        if key not in hidden: hidden.append(key)
        save(self.data); self.draw()

    def restore_removed(self):
        hidden=self.data.get("_hidden", [])
        available=[Path(key) for key in hidden if Path(key).exists()]
        if not available:
            messagebox.showinfo("Restore removed", "There are no removed lectures available to restore.")
            return

        window=tk.Toplevel(self.root)
        window.title("Restore removed lectures")
        window.geometry("620x320")
        window.transient(self.root)
        ttk.Label(window,text="Select lectures to restore:").pack(anchor="w",padx=12,pady=(12,4))
        select_all=tk.BooleanVar(value=False)
        list_frame=ttk.Frame(window)
        list_frame.pack(fill="both",expand=True,padx=12,pady=4)
        checks=[]

        def toggle_all():
            for checked in checks: checked.set(select_all.get())

        ttk.Checkbutton(window,text="Select all",variable=select_all,command=toggle_all).pack(anchor="w",padx=12)
        for p in available:
            checked=tk.BooleanVar(value=False)
            checks.append(checked)
            ttk.Checkbutton(list_frame,text=p.name,variable=checked).pack(anchor="w")

        def restore_selected():
            selected=[index for index,checked in enumerate(checks) if checked.get()]
            if not selected:return
            restored={str(available[index].resolve()) for index in selected}
            self.data["_hidden"]=[key for key in hidden if key not in restored]
            save(self.data); self.draw(); window.destroy()

        buttons=ttk.Frame(window); buttons.pack(fill="x",padx=12,pady=12)
        ttk.Button(buttons,text="Restore selected",command=restore_selected).pack(side="left")
        ttk.Button(buttons,text="Cancel",command=window.destroy).pack(side="right")

    def import_history(self):
        hist=registry_history()
        if not hist:
            messagebox.showinfo("MPC-BE History","No matching previous video paths were found in the common MPC-BE registry locations.")
            return
        names={Path(x).name.lower():x for x in hist}
        changed=0
        for p in vids():
            if p.name.lower() in names:
                # History proves the file was opened, but does not always
                # expose its exact old position. Offer it as watched only
                # if the user confirms.
                pass
        messagebox.showinfo("History found",
            f"Found {len(hist)} previous video entries in MPC-BE history.\n\n"
            "MPC-BE builds store history differently, so this tracker will not falsely "
            "claim a lecture was fully watched just because it was opened.\n\n"
            "Use the right-click menu to mark the lectures you already completed.")

    def loop(self):
        info = getattr(self, "_latest_player_info", None)
        self.current_info = info
        lecture = self.find_current_lecture(info)
        needs_redraw = False
        if info:
            player_name = info.get("player", "Player")
            port = MPC_PORT if player_name == "MPC-BE" else VLC_PORT
            mode_prefix = f"Auto-detect: {player_name}" if PLAYER_MODE == "auto" else player_name
            self.conn.set(f"{mode_prefix} connected • port {port}")
            if lecture:
                r = self.data[str(lecture.resolve())]
                if info["dur"] and r.get("duration") != info["dur"]:
                    r["duration"] = info["dur"]
                    needs_redraw = True
                if info["pos"] > float(r.get("furthest") or 0):
                    r["furthest"] = info["pos"]
                    save(self.data)
                    needs_redraw = True
                d = float(r.get("duration") or info["dur"] or 0)
                f = min(r.get("furthest", 0), d) if d else r.get("furthest", 0)
                pct = f / d * 100 if d else 0
                session_watched = sum(float(s.get("duration") or 0) for s in self.data.get("_sessions", []) if isinstance(s, dict) and str(s.get("lecture", "")).lower() == lecture.name.lower())
                if self.active_segment and self.active_segment["lecture"] == lecture.name:
                    session_watched += self.active_segment["video_elapsed"]
                self.now.set(lecture.name)
                self.nd.set(f"{info['ps']} / {info['ds']} • Covered {fmt(f)} ({pct:.1f}%) • Session watched: {fmt(session_watched)} • {info['state']} ({player_name})")
                self.npb["value"] = pct
            else:
                self.now.set("No recognized lecture currently playing")
                self.nd.set("")
                self.npb["value"] = 0
        else:
            if PLAYER_MODE == "auto":
                self.conn.set(f"Waiting for media player (Auto-detect MPC-BE port {MPC_PORT} / VLC port {VLC_PORT})")
            elif PLAYER_MODE == "mpc":
                self.conn.set(f"MPC-BE Web Interface not connected at port {MPC_PORT}")
            else:
                self.conn.set(f"VLC Web Interface not connected at port {VLC_PORT}")
            self.now.set("No lecture currently playing")
            self.nd.set("")
            self.npb["value"] = 0

        if self.session and self.session["status"] == "active" and self.auto_start.get() and lecture and info and self.auto_block_path == info.get("path"):
            pass
        elif not self.session and self.auto_start.get() and self.is_playing(info) and lecture and self.auto_block_path != info.get("path"):
            self.start_session()
            needs_redraw = True

        # Auto-pause / resume transitions based on media player playback state
        cur_playing = self.is_playing(info)
        prev_playing = getattr(self, "_last_video_playing", None)
        self._last_video_playing = cur_playing

        if self.auto_pause_on_video.get() and self.session and prev_playing is not None:
            if prev_playing and not cur_playing and self.session.get("status") == "active":
                self._auto_paused_session = True
                self.pause_session()
            elif not prev_playing and cur_playing and self.session.get("status") == "paused" and getattr(self, "_auto_paused_session", False):
                self._auto_paused_session = False
                self.start_session()

        self.track_activity(info, lecture)
        if lecture and self.session and self.session["status"] == "active":
            self.timer_lecture_full = lecture.name
            self.timer_lecture.set(self._truncate_lecture(lecture.name))
        elif not lecture and self.session:
            self.timer_lecture_full = ""
            self.timer_lecture.set("Waiting...")
        if self.session:
            self.update_session_display()

        if needs_redraw:
            self.draw()

        # ── Study Reminder countdown ──────────────────────────────────────────
        if self.session and self.session.get("status") == "active" and self.reminder_enabled.get():
            self._reminder_elapsed += 1
            try:
                interval_s = max(1, int(self.reminder_interval.get()))  # already in seconds
            except ValueError:
                interval_s = 2700
            remaining = max(0, interval_s - self._reminder_elapsed)
            rh, rr = divmod(remaining, 3600); rm, rs = divmod(rr, 60)
            self._countdown_var.set(f"{rh:02d}:{rm:02d}:{rs:02d}")
            if self._reminder_elapsed >= interval_s:
                self._reminder_elapsed = 0
                self._fire_reminder()
        else:
            # Show configured interval as static display when not in session
            try:
                total = max(0, int(self.reminder_interval.get()))
            except (ValueError, AttributeError):
                total = 2700
            if self.reminder_enabled.get():
                th, tr = divmod(total, 3600); tm, ts = divmod(tr, 60)
                self._countdown_var.set(f"{th:02d}:{tm:02d}:{ts:02d}")
            else:
                try: self._countdown_var.set("--:--:--")
                except AttributeError: pass
        # ─────────────────────────────────────────────────────────────────────

        self.root.after(1000, self.loop)


if __name__=="__main__":
    r=tk.Tk(); r.withdraw()
    selected = load_last_folder()
    if not selected:
        chosen = filedialog.askdirectory(
            parent=r,
            title="GitVLMPC - Choose your lecture video folder"
        )
        if chosen:
            selected = Path(chosen)
            save_last_folder(str(selected))
    if not selected:
        r.destroy()
    else:
        VIDEO_DIR = selected
        DATA_FILE = VIDEO_DIR / ".lecture_progress.json"
        save_last_folder(str(VIDEO_DIR))
        if not shutil.which("ffprobe"):
            messagebox.showwarning(
                "FFmpeg not found",
                "ffprobe was not found in PATH. Video durations will be detected automatically when playing in MPC-BE or VLC.\n\n"
                "Tip: Installing FFmpeg allows instant duration detection for all files without playing them."
            )
        r.deiconify(); App(r); r.mainloop()
