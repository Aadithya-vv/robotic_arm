"""Tkinter desktop shell for TaskGraph v0.1; contains no Engine business logic."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox,ttk
from health import collect_health
from shutdown import shutdown_runtime
from validation import validate_runtime,validation_passed
from taskgraph_logging import LoggingRequest

class TaskGraphApp:
    COLORS={"bg":"#0b1220","panel":"#111c2f","card":"#17243a","text":"#e5eefc","muted":"#91a4bf","accent":"#4f9cf9","green":"#32d583","red":"#f97066"}
    def __init__(self,runtime,checks,root_path:Path):
        self.runtime=runtime;self.checks=checks;self.root_path=root_path;self._closed=False;self._selected="Runtime"
        self.window=tk.Tk();self.window.title("TaskGraph v0.1 — Core Platform");self.window.geometry("1280x760");self.window.minsize(1024,640);self.window.configure(bg=self.COLORS["bg"]);self.window.protocol("WM_DELETE_WINDOW",self.shutdown)
        self._style();self._build();self._refresh()
    def _style(self):
        style=ttk.Style(self.window);style.theme_use("clam");style.configure("TFrame",background=self.COLORS["bg"]);style.configure("Card.TFrame",background=self.COLORS["panel"]);style.configure("TLabel",background=self.COLORS["bg"],foreground=self.COLORS["text"],font=("Segoe UI",10));style.configure("Title.TLabel",font=("Segoe UI Semibold",22),foreground=self.COLORS["text"]);style.configure("Muted.TLabel",foreground=self.COLORS["muted"]);style.configure("TButton",font=("Segoe UI Semibold",10),padding=9,background=self.COLORS["card"],foreground=self.COLORS["text"]);style.map("TButton",background=[("active",self.COLORS["accent"])]);style.configure("Treeview",background=self.COLORS["panel"],fieldbackground=self.COLORS["panel"],foreground=self.COLORS["text"],rowheight=28,borderwidth=0);style.configure("Treeview.Heading",background=self.COLORS["card"],foreground=self.COLORS["text"])
    def _build(self):
        top=ttk.Frame(self.window,padding=(22,16));top.pack(fill="x");ttk.Label(top,text="TaskGraph",style="Title.TLabel").pack(side="left");ttk.Label(top,text="v0.1  •  Core Platform",style="Muted.TLabel").pack(side="left",padx=16);self.status=ttk.Label(top,text="● Runtime Online",foreground=self.COLORS["green"]);self.status.pack(side="right")
        body=ttk.Frame(self.window,padding=(16,0,16,10));body.pack(fill="both",expand=True)
        left=ttk.Frame(body,style="Card.TFrame",padding=12);left.pack(side="left",fill="y");ttk.Label(left,text="CORE PLATFORM",style="Muted.TLabel",background=self.COLORS["panel"]).pack(anchor="w",pady=(0,8))
        for name in ("Runtime","Bootstrap","Kernel","Configuration","Registry","Event Bus","Memory","Logging"):
            ttk.Button(left,text=name,command=lambda n=name:self._select(n)).pack(fill="x",pady=3)
        center=ttk.Frame(body,style="Card.TFrame",padding=16);center.pack(side="left",fill="both",expand=True,padx=12);ttk.Label(center,text="Activity Timeline",font=("Segoe UI Semibold",14),background=self.COLORS["panel"],foreground=self.COLORS["text"]).pack(anchor="w");self.timeline=tk.Text(center,bg=self.COLORS["panel"],fg=self.COLORS["text"],insertbackground=self.COLORS["text"],relief="flat",font=("Cascadia Mono",9),state="disabled",wrap="word");self.timeline.pack(fill="both",expand=True,pady=(10,0))
        right=ttk.Frame(body,style="Card.TFrame",padding=16,width=280);right.pack(side="right",fill="y");right.pack_propagate(False);ttk.Label(right,text="Engine Details",font=("Segoe UI Semibold",14),background=self.COLORS["panel"],foreground=self.COLORS["text"]).pack(anchor="w");self.details={}
        for key in ("Name","Status","State","Health","Version","Lifecycle"):
            ttk.Label(right,text=key.upper(),style="Muted.TLabel",background=self.COLORS["panel"]).pack(anchor="w",pady=(16,2));value=ttk.Label(right,text="—",background=self.COLORS["panel"],foreground=self.COLORS["text"]);value.pack(anchor="w");self.details[key]=value
        bottom=ttk.Frame(self.window,padding=(16,8,16,16));bottom.pack(fill="x");ttk.Button(bottom,text="Run Validation",command=self.run_validation).pack(side="left");ttk.Button(bottom,text="Export Report",command=self.export_report).pack(side="left",padx=8);ttk.Button(bottom,text="Shutdown",command=self.shutdown).pack(side="right")
    def _select(self,name):self._selected=name;self._refresh_details()
    def _refresh_details(self):
        health=collect_health(self.runtime)
        if self._selected=="Runtime":
            values={"Name":"Core Platform","Status":"Running","State":"composed","Health":"PASS" if all(x.healthy for x in health.values()) else "FAIL","Version":"v0.1","Lifecycle":"Seven Engines"}
        else:
            item=health[self._selected];values={"Name":f"{item.engine_id} {item.name}","Status":"Online" if item.healthy else "Attention","State":item.state,"Health":"Healthy" if item.healthy else item.detail,"Version":item.version,"Lifecycle":"Operational" if item.healthy else "Unexpected state"}
        for key,value in values.items():self.details[key].configure(text=value)
    def _refresh(self):
        if self._closed:return
        response=self.runtime.logging.query(LoggingRequest("ui-logs","ui-live","desktop-ui"));lines=list(self.runtime.activities)+[f"{x.sequence:04d}  {x.severity.value.upper():8}  {x.source_identity}  {x.message}" for x in response.snapshot.records[-100:]]
        self.timeline.configure(state="normal");self.timeline.delete("1.0","end");self.timeline.insert("end","\n".join(lines));self.timeline.see("end");self.timeline.configure(state="disabled");self._refresh_details();self.window.after(1000,self._refresh)
    def run_validation(self):
        self.checks=validate_runtime(self.runtime,"ui-validation");message="\n".join(f"{'PASS' if x.passed else 'FAIL'} — {x.name}: {x.detail}" for x in self.checks);messagebox.showinfo("Core Platform Validation",message)
    def export_report(self):
        target=self.root_path/"Assets"/"TaskGraph_v0.1_RuntimeExport.json";target.parent.mkdir(parents=True,exist_ok=True);health=collect_health(self.runtime);payload={"version":"v0.1","release":"Core Platform","exported_at":datetime.now().isoformat(),"healthy":all(x.healthy for x in health.values()),"engines":{k:{"id":v.engine_id,"state":v.state,"healthy":v.healthy,"version":v.version} for k,v in health.items()},"validation":[{"name":x.name,"passed":x.passed,"detail":x.detail} for x in self.checks]};target.write_text(json.dumps(payload,indent=2),encoding="utf-8");messagebox.showinfo("Export Report",f"Exported to\n{target}")
    def shutdown(self):
        if self._closed:return
        self._closed=True;results=shutdown_runtime(self.runtime);failed=[name for name,value in results.items() if value.status.value!="succeeded"]
        if failed:messagebox.showerror("Shutdown",f"Shutdown failures: {', '.join(failed)}")
        self.window.destroy()
    def run(self):self.window.mainloop()
