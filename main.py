import json, os, re, shutil, subprocess, tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog, filedialog
from urllib.request import urlopen
from urllib.parse import unquote
import winreg

VIDEO_DIR = None
DATA_FILE = None
MPC_PORT = 13579
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
        self.data=load(); self.build(); self.refresh(); root.after(1000,self.loop)

    def build(self):
        f=ttk.Frame(self.root,padding=14); f.pack(fill="x")
        ttk.Label(f,text="CMP2 Lecture Progress",font=("Segoe UI",21,"bold")).pack(anchor="w")
        ttk.Label(f,text=str(VIDEO_DIR),foreground="#666").pack(anchor="w")
        s=ttk.Frame(f); s.pack(fill="x",pady=10)
        self.vars=[tk.StringVar() for _ in range(4)]
        for v in self.vars: ttk.Label(s,textvariable=v,font=("Segoe UI",11)).pack(side="left",padx=(0,25))
        self.pb=ttk.Progressbar(f,maximum=100); self.pb.pack(fill="x")
        n=ttk.LabelFrame(self.root,text="Currently Playing",padding=10); n.pack(fill="x",padx=14,pady=10)
        self.now=tk.StringVar(value="Waiting for MPC-BE...")
        self.nd=tk.StringVar()
        self.npb=ttk.Progressbar(n,maximum=100); ttk.Label(n,textvariable=self.now,font=("Segoe UI",11,"bold")).pack(anchor="w")
        self.npb.pack(fill="x",pady=5); ttk.Label(n,textvariable=self.nd).pack(anchor="w")
        body=ttk.Frame(self.root,padding=(14,0,14,10)); body.pack(fill="both",expand=True)
        cols=("lecture","status","covered","duration","progress"); self.tree=ttk.Treeview(body,columns=cols,show="headings")
        self.sort_column="lecture"; self.sort_reverse=False
        for c,t,w in zip(cols,("Lecture","Status","Covered","Duration","Progress"),(550,120,130,130,100)):
            self.tree.heading(c,text=t,command=lambda column=c: self.sort_tree(column))
            self.tree.column(c,width=w,anchor="w" if c=="lecture" else "center")
        self.tree.pack(side="left",fill="both",expand=True)
        sc=ttk.Scrollbar(body,command=self.tree.yview); sc.pack(side="right",fill="y"); self.tree.configure(yscrollcommand=sc.set)
        self.tree.bind("<Button-3>",self.menu)
        b=ttk.Frame(self.root,padding=(14,0,14,14)); b.pack(fill="x")
        ttk.Button(b,text="Refresh",command=self.refresh).pack(side="left")
        ttk.Button(b,text="Import MPC-BE History",command=self.import_history).pack(side="left",padx=7)
        ttk.Button(b,text="Open Folder",command=lambda:os.startfile(str(VIDEO_DIR))).pack(side="left")
        self.conn=tk.StringVar(); ttk.Label(b,textvariable=self.conn,foreground="#666").pack(side="right")

    def refresh(self):
        for p in vids():
            k=str(p.resolve()); r=self.data.setdefault(k,{"name":p.name,"duration":0,"furthest":0,"manual":False})
            if not r.get("duration"):
                d=duration_ffprobe(p)
                if d:r["duration"]=d
        save(self.data); self.draw()

    def draw(self):
        self.tree.delete(*self.tree.get_children()); total=covered=0
        rows=[]
        for p in vids():
            r=self.data[str(p.resolve())]; d=float(r.get("duration") or 0); f=float(r.get("furthest") or 0)
            if d:f=min(f,d)
            total+=d; covered+=f
            status="✓ Watched" if d and f>=d-2 else ("◐ In progress" if f>0 else "○ Not watched")
            rows.append((p, status, d, f))
        sort_index={"lecture":0,"status":1,"covered":3,"duration":2,"progress":3}[self.sort_column]
        rows.sort(key=lambda row: row[sort_index].lower() if sort_index in (0,1) else row[sort_index], reverse=self.sort_reverse)
        for p,status,d,f in rows:
            self.tree.insert("", "end", iid=str(p.resolve()), values=(p.name,status,fmt(f),fmt(d) if d else "Unknown",f"{f/d*100:.1f}%" if d else "—"))
        pct=covered/total*100 if total else 0
        self.vars[0].set("Total: "+big(total)); self.vars[1].set("Covered: "+big(covered))
        self.vars[2].set("Remaining: "+big(max(0,total-covered))); self.vars[3].set(f"Overall: {pct:.1f}%"); self.pb["value"]=pct

    def sort_tree(self,column):
        if self.sort_column==column:
            self.sort_reverse=not self.sort_reverse
        else:
            self.sort_column=column; self.sort_reverse=False
        self.draw()

    def selected(self):
        s=self.tree.selection()
        return Path(s[0]) if s else None

    def menu(self,e):
        iid=self.tree.identify_row(e.y)
        if not iid:return
        self.tree.selection_set(iid)
        p=Path(iid)
        m=tk.Menu(self.root,tearoff=0)
        m.add_command(label="✓ Mark as watched",command=lambda: self.watched(p))
        m.add_command(label="○ Mark as not watched",command=lambda: self.unwatched(p))
        m.add_command(label="Set covered time...",command=lambda: self.settime(p))
        m.add_command(label="Set to current MPC-BE position",command=lambda: self.set_current(p))
        try:
            m.tk_popup(e.x_root,e.y_root)
        finally:
            m.grab_release()

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
        info=mpc()
        if info:
            self.conn.set(f"MPC-BE connected • port {MPC_PORT}")
            p=Path(info["path"]); match=None
            for v in vids():
                if v.name.lower()==p.name.lower(): match=v;break
            if match:
                r=self.data[str(match.resolve())]
                if info["dur"]:r["duration"]=info["dur"]
                if info["pos"]>float(r.get("furthest") or 0):
                    r["furthest"]=info["pos"]; save(self.data)
                d=float(r.get("duration") or info["dur"] or 0); f=min(r.get("furthest",0),d) if d else r.get("furthest",0)
                pct=f/d*100 if d else 0
                self.now.set(match.name); self.nd.set(f"{info['ps']} / {info['ds']} • Covered {fmt(f)} ({pct:.1f}%) • {info['state']}")
                self.npb["value"]=pct; self.draw()
        else:
            self.conn.set(f"MPC-BE Web Interface not connected at port {MPC_PORT}")
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
