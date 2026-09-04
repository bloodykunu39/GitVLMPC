import base64, json, math, os, re, shutil, subprocess, tkinter as tk, time
from datetime import datetime
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

def vids():
    return sorted([p for p in VIDEO_DIR.iterdir() if p.is_file() and p.suffix.lower() in EXTS],
                  key=lambda x:x.name.lower()) if VIDEO_DIR.exists() else []

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
    try:
        with urlopen(f"http://127.0.0.1:{port}/variables.html",timeout=1) as r:
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
    password = password if password is not None else VLC_PASSWORD
    try:
        url = f"http://127.0.0.1:{port}/requests/status.json"
        auth_bytes = f":{password}".encode("utf-8")
        auth_header = "Basic " + base64.b64encode(auth_bytes).decode("ascii")
        req = Request(url, headers={"Authorization": auth_header, "User-Agent": "LectureProgressTracker"})
        with urlopen(req, timeout=1) as r:
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

class App:
    def __init__(self,root):
        self.root=root; self.root.title("GitVLMPC - Lecture Progress Tracker"); self.root.geometry("1120x720")
        self.folder_var=tk.StringVar(value=str(VIDEO_DIR))
        self.search_var=tk.StringVar()
        self.current_theme = load_app_theme()
        self.data=load(); self.load_settings(); self.session=None; self.active_segment=None; self.current_info=None; self.auto_block_path=None
        self.build()
        self.apply_theme(self.current_theme)
        self.refresh()
        root.after(400,self.check_first_run)
        root.after(1000,self.loop)
        root.after(10000,self.auto_refresh)
        root.protocol("WM_DELETE_WINDOW",self.close)

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
        self.main_canvas = tk.Canvas(self.root, highlightthickness=0)
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

        def _on_mousewheel(event):
            if not event.delta:
                return
            count = int(-1 * (event.delta / 120))
            step = count if count != 0 else (-1 if event.delta > 0 else 1)

            target = self.root.winfo_containing(event.x_root, event.y_root)
            tree_widget = None
            w = target
            while w:
                w_str = str(w).lower()
                if "treeview" in w_str:
                    tree_widget = w
                    break
                w = getattr(w, "master", None)

            if tree_widget:
                try:
                    first, last = tree_widget.yview()
                    if step > 0 and last < 0.999:
                        tree_widget.yview_scroll(step, "units")
                        return "break"
                    elif step < 0 and first > 0.001:
                        tree_widget.yview_scroll(step, "units")
                        return "break"
                except Exception:
                    pass

            self.main_canvas.yview_scroll(step * 2, "units")
            return "break"

        self.main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

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
        
        timer=ttk.LabelFrame(self.content,text="Study Stopwatch",padding=10); timer.pack(fill="x",padx=14,pady=(0,10))
        self.timer_text=tk.StringVar(value="00:00:00"); self.timer_lecture=tk.StringVar(value="Waiting for media player activity")
        ttk.Label(timer,textvariable=self.timer_lecture,font=("Segoe UI",10,"bold")).pack(side="left")
        
        self.timer_badge=tk.Frame(timer,padx=10,pady=2,relief="solid",borderwidth=1)
        self.timer_badge.pack(side="left",padx=14)
        self.timer_label=tk.Label(self.timer_badge,textvariable=self.timer_text,font=("Consolas",15,"bold"))
        self.timer_label.pack()

        self.start_session_button=ttk.Button(timer,text="Start Session",command=self.start_session); self.start_session_button.pack(side="left")
        self.pause_session_button=ttk.Button(timer,text="Pause Session",command=self.pause_session,state="disabled"); self.pause_session_button.pack(side="left",padx=6)
        self.stop_session_button=ttk.Button(timer,text="End Session",command=self.stop_session,state="disabled"); self.stop_session_button.pack(side="left")
        self.auto_start=tk.BooleanVar(value=self.auto_start_value)
        ttk.Checkbutton(timer,text="Auto-start when player is playing",variable=self.auto_start,command=self.save_auto_start).pack(side="left",padx=8)
        ttk.Button(timer,text="Session History",command=self.show_sessions).pack(side="left",padx=6)
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
        # Bottom bar for multi-selection mode
        bottom_bar=ttk.Frame(self.content,padding=(14,4,14,8)); bottom_bar.pack(fill="x")
        self.select_all_button=ttk.Button(bottom_bar,text="Select all",command=self.select_all)
        self.unselect_all_button=ttk.Button(bottom_bar,text="Unselect all",command=self.unselect_all)
        self.done_selecting_button=ttk.Button(bottom_bar,text="Done",command=self.exit_select_mode)
        self.selected_count=tk.StringVar(value="")
        self.selected_count_label=ttk.Label(bottom_bar,textvariable=self.selected_count,foreground="#666")

    def refresh(self):
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
        self.refresh()
        self.root.after(10000,self.auto_refresh)

    def change_folder(self):
        global VIDEO_DIR, DATA_FILE
        selected=filedialog.askdirectory(parent=self.root,initialdir=str(VIDEO_DIR) if VIDEO_DIR else None,title="Choose your lecture video folder")
        if not selected:return
        self.stop_session(save_session=True)
        self.exit_select_mode()
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
        self.tree.delete(*self.tree.get_children()); total=covered=0; ratings=[]
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
        for p,status,d,f,rating,review,spent in rows:
            checkbox="☑" if str(p.resolve()) in self.checked else "☐"
            if not self.select_mode: checkbox=""
            rating_text=f"{rating:g}/5" if 1<=rating<=5 else "—"
            tag="watched" if d and f>=d-2 else ("progress" if f>0 else "unwatched")
            self.tree.insert("", "end", iid=str(p.resolve()), values=(checkbox,p.name,status,fmt(f),fmt(d) if d else "Unknown",f"{f/d*100:.1f}%" if d else "—",rating_text,review,fmt(spent)),tags=(tag,))
        pct=covered/total*100 if total else 0
        self.vars[0].set("Total: "+big(total)); self.vars[1].set("Covered: "+big(covered))
        self.vars[2].set("Remaining: "+big(max(0,total-covered))); self.vars[3].set(f"Overall: {pct:.1f}%")
        self.vars[4].set(f"Avg rating: {sum(ratings)/len(ratings):.1f}/5" if ratings else "Avg rating: —")
        self.vars[5].set("Study time: "+big(study_total))
        self.pb["value"]=pct
        self.selected_count.set(f"{len(self.checked)} selected" if self.select_mode else "")
        self.draw_activity()

    def draw_activity(self):
        self.activity_tree.delete(*self.activity_tree.get_children())
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
        for segment in sessions:
            if not isinstance(segment,dict):continue
            started=str(segment.get("started_at", ""))
            self.activity_tree.insert("","end",values=(segment.get("session_name",""),segment.get("lecture",""),started.replace("T"," "),fmt(segment.get("session_duration",segment.get("duration",0))),fmt(segment.get("video_play_duration",segment.get("duration",0)))))

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
        if self.select_mode and str(p.resolve()) in self.checked:
            m.add_command(label="Remove all selected",command=lambda: self.remove_selected())
        else:
            m.add_command(label="Remove from tracker",command=lambda: self.context_remove(p))
        try:
            m.tk_popup(e.x_root,e.y_root)
        finally:
            m.grab_release()

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
        paths=self.context_paths(p); info=self.current_info or poll_player()
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
            self.session["status"]="active"; self.session["resumed_at"]=datetime.now().isoformat(timespec="seconds"); self.update_session_display(); return
        if self.session:return
        counter=int(self.data.get("_session_counter",0) or 0)+1
        self.data["_session_counter"]=counter
        self.session={"id":f"Session{counter:04d}","status":"active","started_at":datetime.now().isoformat(timespec="seconds"),"total":0,"video_total":0,"segments":[]}
        save(self.data)
        self.auto_block_path=None; self.update_session_display()

    def pause_session(self):
        if not self.session:return
        self.track_activity(self.current_info,self.find_current_lecture(self.current_info)); self.finish_segment(); self.session["status"]="paused"; self.update_session_display(); save(self.data)

    def stop_session(self,save_session=True):
        if not self.session:return
        self.track_activity(self.current_info,self.find_current_lecture(self.current_info)); self.finish_segment()
        if save_session:
            completed=dict(self.session); completed["ended_at"]=datetime.now().isoformat(timespec="seconds")
            completed.pop("status",None); completed.pop("segments",None)
            completed["segments"]=self.session.get("segments",[])
            self.data.setdefault("_study_sessions",[]).append(completed); save(self.data)
        if self.current_info:self.auto_block_path=self.current_info.get("path")
        self.session=None; self.active_segment=None; self.timer_text.set("00:00:00"); self.timer_lecture.set("Waiting for media player activity"); self.update_session_display(); self.draw()

    def close(self):
        self.stop_session(save_session=True); self.root.destroy()

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
        p=p or self.selected(); info=self.current_info or poll_player()
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
        info=poll_player(); self.current_info=info
        lecture=self.find_current_lecture(info)
        if info:
            player_name=info.get("player","Player")
            port=MPC_PORT if player_name=="MPC-BE" else VLC_PORT
            mode_prefix=f"Auto-detect: {player_name}" if PLAYER_MODE=="auto" else player_name
            self.conn.set(f"{mode_prefix} connected • port {port}")
            if lecture:
                r=self.data[str(lecture.resolve())]
                if info["dur"]:r["duration"]=info["dur"]
                if info["pos"]>float(r.get("furthest") or 0):r["furthest"]=info["pos"]; save(self.data)
                d=float(r.get("duration") or info["dur"] or 0); f=min(r.get("furthest",0),d) if d else r.get("furthest",0)
                pct=f/d*100 if d else 0
                session_watched=sum(float(s.get("duration") or 0) for s in self.data.get("_sessions",[]) if isinstance(s,dict) and str(s.get("lecture","")).lower()==lecture.name.lower())
                if self.active_segment and self.active_segment["lecture"]==lecture.name:session_watched+=self.active_segment["video_elapsed"]
                self.now.set(lecture.name); self.nd.set(f"{info['ps']} / {info['ds']} • Covered {fmt(f)} ({pct:.1f}%) • Session watched: {fmt(session_watched)} • {info['state']} ({player_name})"); self.npb["value"]=pct
            else:
                self.now.set("No recognized lecture currently playing"); self.nd.set(""); self.npb["value"]=0
        else:
            if PLAYER_MODE=="auto":
                self.conn.set(f"Waiting for media player (Auto-detect MPC-BE port {MPC_PORT} / VLC port {VLC_PORT})")
            elif PLAYER_MODE=="mpc":
                self.conn.set(f"MPC-BE Web Interface not connected at port {MPC_PORT}")
            else:
                self.conn.set(f"VLC Web Interface not connected at port {VLC_PORT}")
            self.now.set("No lecture currently playing"); self.nd.set(""); self.npb["value"]=0
        if self.session and self.session["status"]=="active" and self.auto_start.get() and lecture and info and self.auto_block_path==info.get("path"):
            pass
        elif not self.session and self.auto_start.get() and self.is_playing(info) and lecture and self.auto_block_path!=info.get("path"):
            self.start_session()
        self.track_activity(info,lecture)
        if lecture and self.session and self.session["status"]=="active":
            self.timer_lecture.set(lecture.name)
        elif not lecture and self.session:
            self.timer_lecture.set("Waiting for recognized lecture")
        if self.session:self.update_session_display()
        self.draw()
        self.root.after(1000,self.loop)

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
