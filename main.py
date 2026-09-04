import json, os, re, shutil, subprocess, tkinter as tk, time
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog, filedialog
from urllib.request import urlopen
from urllib.parse import unquote
import winreg

VIDEO_DIR = None
DATA_FILE = None
DEFAULT_MPC_PORT = 13579
MPC_PORT = DEFAULT_MPC_PORT
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

def mpc():
    try:
        with urlopen(f"http://127.0.0.1:{MPC_PORT}/variables.html",timeout=1) as r:
            h=r.read().decode("utf-8","replace")
        return {"path":unquote(tag(h,"filepath")),
                "pos":float(tag(h,"position") or 0)/1000,
                "dur":float(tag(h,"duration") or 0)/1000,
                "ps":tag(h,"positionstring"),"ds":tag(h,"durationstring"),
                "state":tag(h,"statestring")}
    except: return None

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
        self.root=root; self.root.title("MPC-BE Lecture Progress"); self.root.geometry("1120x720")
        self.folder_var=tk.StringVar(value=str(VIDEO_DIR))
        self.search_var=tk.StringVar()
        self.data=load(); self.load_settings(); self.session=None; self.active_segment=None; self.current_info=None; self.auto_block_path=None; self.build(); self.refresh(); root.after(1000,self.loop)
        root.after(10000,self.auto_refresh)
        root.protocol("WM_DELETE_WINDOW",self.close)

    def build(self):
        f=ttk.Frame(self.root,padding=14); f.pack(fill="x")
        ttk.Label(f,text="CMP2 Lecture Progress",font=("Segoe UI",21,"bold")).pack(anchor="w")
        ttk.Label(f,textvariable=self.folder_var,foreground="#666").pack(anchor="w")
        search=ttk.Frame(f); search.pack(fill="x",pady=(8,0))
        ttk.Label(search,text="Search:").pack(side="left")
        ttk.Entry(search,textvariable=self.search_var,width=42).pack(side="left",padx=7)
        ttk.Button(search,text="Change Folder",command=self.change_folder).pack(side="left")
        self.search_var.trace_add("write",lambda *_: self.draw())
        s=ttk.Frame(f); s.pack(fill="x",pady=10)
        self.vars=[tk.StringVar() for _ in range(6)]
        for v in self.vars: ttk.Label(s,textvariable=v,font=("Segoe UI",11)).pack(side="left",padx=(0,25))
        self.pb=ttk.Progressbar(f,maximum=100); self.pb.pack(fill="x")
        n=ttk.LabelFrame(self.root,text="Currently Playing",padding=10); n.pack(fill="x",padx=14,pady=10)
        self.now=tk.StringVar(value="Waiting for MPC-BE...")
        self.nd=tk.StringVar()
        self.npb=ttk.Progressbar(n,maximum=100); ttk.Label(n,textvariable=self.now,font=("Segoe UI",11,"bold")).pack(anchor="w")
        self.npb.pack(fill="x",pady=5); ttk.Label(n,textvariable=self.nd).pack(anchor="w")
        timer=tk.LabelFrame(self.root,text="Study stopwatch",padx=10,pady=8); timer.pack(fill="x",padx=14,pady=(0,10))
        self.timer_text=tk.StringVar(value="00:00:00"); self.timer_lecture=tk.StringVar(value="Waiting for MPC-BE activity")
        ttk.Label(timer,textvariable=self.timer_lecture,font=("Segoe UI",10,"bold")).pack(side="left")
        ttk.Label(timer,textvariable=self.timer_text,font=("Segoe UI",16,"bold")).pack(side="left",padx=18)
        self.start_session_button=ttk.Button(timer,text="Start Session",command=self.start_session); self.start_session_button.pack(side="left")
        self.pause_session_button=ttk.Button(timer,text="Pause Session",command=self.pause_session,state="disabled"); self.pause_session_button.pack(side="left",padx=6)
        self.stop_session_button=ttk.Button(timer,text="End Session",command=self.stop_session,state="disabled"); self.stop_session_button.pack(side="left")
        self.auto_start=tk.BooleanVar(value=self.auto_start_value)
        ttk.Checkbutton(timer,text="Auto-start when MPC-BE is playing",variable=self.auto_start,command=self.save_auto_start).pack(side="left",padx=8)
        ttk.Button(timer,text="Session History",command=self.show_sessions).pack(side="left",padx=6)
        self.activity_frame=ttk.LabelFrame(self.root,text="Session activity",padding=6)
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
        self.show_activity_button=ttk.Button(self.root,text="Show Activity",command=self.show_activity)
        body=ttk.Frame(self.root,padding=(14,0,14,10)); body.pack(fill="both",expand=True)
        cols=("select","lecture","status","covered","duration","progress","rating","review","spent"); self.tree=ttk.Treeview(body,columns=cols,show="headings")
        self.sort_column="lecture"; self.sort_reverse=False
        self.select_mode=False; self.checked=set()
        for c,t,w in zip(cols,("Select","Lecture","Status","Covered","Duration","Progress","Rating","Review","Time Spent"),(0,390,120,105,105,85,70,250,100)):
            self.tree.heading(c,text=t,command=lambda column=c: self.sort_tree(column))
            self.tree.column(c,width=w,anchor="w" if c=="lecture" else "center",stretch=c!="select")
        self.tree.pack(side="left",fill="both",expand=True)
        self.tree.tag_configure("watched",background="#e8f5e9")
        self.tree.tag_configure("progress",background="#fff8e1")
        self.tree.tag_configure("unwatched",background="#ffebee")
        sc=ttk.Scrollbar(body,command=self.tree.yview); sc.pack(side="right",fill="y"); self.tree.configure(yscrollcommand=sc.set)
        self.tree.bind("<Button-3>",self.menu)
        self.tree.bind("<Button-1>",self.tree_click)
        self.tree.bind("<Double-1>",self.open_lecture)
        toolbar=ttk.Frame(self.root,padding=(14,0,14,0)); toolbar.pack(fill="x")
        toolbar_canvas=tk.Canvas(toolbar,height=36,highlightthickness=0)
        toolbar_scroll=ttk.Scrollbar(toolbar,orient="horizontal",command=toolbar_canvas.xview)
        toolbar_canvas.configure(xscrollcommand=toolbar_scroll.set)
        toolbar_canvas.pack(fill="x")
        toolbar_scroll.pack(fill="x")
        b=ttk.Frame(toolbar_canvas)
        toolbar_canvas.create_window((0,0),window=b,anchor="nw")
        b.bind("<Configure>",lambda e: toolbar_canvas.configure(scrollregion=toolbar_canvas.bbox("all")))
        ttk.Button(b,text="Refresh",command=self.refresh).pack(side="left")
        ttk.Button(b,text="Import MPC-BE History",command=self.import_history).pack(side="left",padx=7)
        ttk.Button(b,text="Open Folder",command=lambda:os.startfile(str(VIDEO_DIR))).pack(side="left")
        ttk.Button(b,text="Restore Removed",command=self.restore_removed).pack(side="left",padx=7)
        ttk.Button(b,text="MPC Settings",command=self.configure_mpc).pack(side="left",padx=7)
        ttk.Button(b,text="Test MPC",command=self.test_mpc).pack(side="left")
        ttk.Button(b,text="Export Progress",command=self.export_progress).pack(side="left",padx=7)
        ttk.Button(b,text="Import Progress",command=self.import_progress).pack(side="left")
        self.select_all_button=ttk.Button(b,text="Select all",command=self.select_all)
        self.unselect_all_button=ttk.Button(b,text="Unselect all",command=self.unselect_all)
        self.done_selecting_button=ttk.Button(b,text="Done",command=self.exit_select_mode)
        self.selected_count=tk.StringVar(value="")
        self.selected_count_label=ttk.Label(b,textvariable=self.selected_count,foreground="#666")
        self.conn=tk.StringVar(); ttk.Label(self.root,textvariable=self.conn,foreground="#666").pack(anchor="e",padx=14,pady=(2,10))

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
        selected=filedialog.askdirectory(parent=self.root,initialdir=str(VIDEO_DIR),title="Choose your lecture video folder")
        if not selected:return
        self.stop_session(save_session=True)
        self.exit_select_mode()
        VIDEO_DIR=Path(selected); DATA_FILE=VIDEO_DIR / ".lecture_progress.json"
        self.folder_var.set(str(VIDEO_DIR)); self.data=load(); self.load_settings(); self.refresh()

    def load_settings(self):
        global MPC_PORT
        MPC_PORT=DEFAULT_MPC_PORT
        try:
            port=int(self.data.get("_settings",{}).get("mpc_port",DEFAULT_MPC_PORT))
            if 1<=port<=65535:MPC_PORT=port
        except (TypeError,ValueError): pass
        self.auto_start_value=bool(self.data.get("_settings",{}).get("auto_start",True))

    def configure_mpc(self):
        global MPC_PORT
        value=simpledialog.askstring("MPC-BE settings","MPC-BE web interface port:",initialvalue=str(MPC_PORT),parent=self.root)
        if value is None:return
        try:
            port=int(value)
            if not 1<=port<=65535:raise ValueError
        except ValueError:
            messagebox.showerror("Invalid port","Enter a port number from 1 to 65535.")
            return
        MPC_PORT=port
        self.data.setdefault("_settings",{})["mpc_port"]=port
        save(self.data); self.conn.set(f"MPC-BE port changed to {MPC_PORT}; testing..."); self.test_mpc()

    def test_mpc(self):
        info=mpc()
        if info:
            messagebox.showinfo("MPC-BE connection",f"Connected to MPC-BE on port {MPC_PORT}.")
        else:
            messagebox.showwarning("MPC-BE connection",f"Could not connect on port {MPC_PORT}. Check MPC-BE's web interface settings.")

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

    def hide_activity(self):
        self.activity_frame.pack_forget()
        self.show_activity_button.pack(fill="x",padx=14,pady=(0,10))

    def show_activity(self):
        self.show_activity_button.pack_forget()
        self.activity_frame.pack(fill="x",padx=14,pady=(0,10),before=self.root.winfo_children()[-1])

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

    def selected(self):
        s=self.tree.selection()
        return Path(s[0]) if s else None

    def menu(self,e):
        iid=self.tree.identify_row(e.y)
        if not iid:return
        self.tree.selection_set(iid)
        p=Path(iid)
        bulk=self.select_mode and str(p.resolve()) in self.checked
        m=tk.Menu(self.root,tearoff=0)
        m.add_command(label="Unselect" if bulk else "Select",command=lambda: self.toggle_select(p))
        m.add_separator()
        m.add_command(label="✓ Mark all selected as watched" if bulk else "✓ Mark as watched",command=lambda: self.context_watched(p,True))
        m.add_command(label="○ Mark all selected as not watched" if bulk else "○ Mark as not watched",command=lambda: self.context_watched(p,False))
        m.add_command(label="Set covered time for all selected..." if bulk else "Set covered time...",command=lambda: self.context_settime(p))
        m.add_command(label="Set all selected to current MPC-BE position" if bulk else "Set to current MPC-BE position",command=lambda: self.context_set_current(p))
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
        paths=self.context_paths(p); info=mpc()
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
            self.timer_lecture.set("Waiting for MPC-BE activity")
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
        self.session=None; self.active_segment=None; self.timer_text.set("00:00:00"); self.timer_lecture.set("Waiting for MPC-BE activity"); self.update_session_display(); self.draw()

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
            if value and not 1<=value<=5:
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
            if rating!=0 and not 1<=rating<=5:raise ValueError
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
        p=p or self.selected(); info=mpc()
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
        info=mpc(); self.current_info=info
        lecture=self.find_current_lecture(info)
        if info:
            self.conn.set(f"MPC-BE connected • port {MPC_PORT}")
            if lecture:
                r=self.data[str(lecture.resolve())]
                if info["dur"]:r["duration"]=info["dur"]
                if info["pos"]>float(r.get("furthest") or 0):r["furthest"]=info["pos"]; save(self.data)
                d=float(r.get("duration") or info["dur"] or 0); f=min(r.get("furthest",0),d) if d else r.get("furthest",0)
                pct=f/d*100 if d else 0
                session_watched=sum(float(s.get("duration") or 0) for s in self.data.get("_sessions",[]) if isinstance(s,dict) and str(s.get("lecture","")).lower()==lecture.name.lower())
                if self.active_segment and self.active_segment["lecture"]==lecture.name:session_watched+=self.active_segment["video_elapsed"]
                self.now.set(lecture.name); self.nd.set(f"{info['ps']} / {info['ds']} • Covered {fmt(f)} ({pct:.1f}%) • Session watched: {fmt(session_watched)} • {info['state']}"); self.npb["value"]=pct
            else:
                self.now.set("No recognized lecture currently playing"); self.nd.set(""); self.npb["value"]=0
        else:
            self.conn.set(f"MPC-BE Web Interface not connected at port {MPC_PORT}"); self.now.set("No lecture currently playing"); self.nd.set(""); self.npb["value"]=0
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
    selected=filedialog.askdirectory(
        parent=r,
        title="Choose your lecture video folder"
    )
    if not selected:
        r.destroy()
    else:
        VIDEO_DIR=Path(selected)
        DATA_FILE=VIDEO_DIR / ".lecture_progress.json"
        if not shutil.which("ffprobe"):
            messagebox.showwarning(
                "FFmpeg not found",
                "ffprobe was not found in PATH. Video durations may show as Unknown.\n\n"
                "Install FFmpeg and add its bin folder to PATH for automatic duration detection."
            )
        r.deiconify(); App(r); r.mainloop()
