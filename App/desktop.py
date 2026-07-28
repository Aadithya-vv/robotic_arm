"""TaskGraph v0.4 video-first robotic teaching workstation."""
from __future__ import annotations

import json
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime
from pathlib import Path
from time import monotonic
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from gpu_runtime import accelerator_diagnostics
from health import collect_health
from object_dialogs import ObjectDetailsDialog, ObjectLibraryWindow
from shutdown import shutdown_runtime
from taskgraph_logging import LoggingRequest
from validation import validate_runtime, validation_passed


class TaskGraphApp:
    COLORS = {"bg":"#0b1220","panel":"#111c2f","card":"#17243a","text":"#e5eefc","muted":"#91a4bf","accent":"#4f9cf9","green":"#32d583","red":"#f97066","yellow":"#fdb022"}

    def __init__(self, runtime, checks, root_path: Path):
        self.runtime, self.checks, self.root_path = runtime, checks, Path(root_path)
        self.video = runtime.video_workspace
        self._closed, self._started, self.current_frame = False, monotonic(), 0
        self.current_task, self.last_operation, self.progress_value, self.eta_value = "Idle", "Startup complete", 0, 0
        self.window = tk.Tk()
        self.window.title("TaskGraph")
        self.window.geometry("1440x900"); self.window.minsize(1100, 700)
        self.window.configure(bg=self.COLORS["bg"]); self.window.protocol("WM_DELETE_WINDOW", self.shutdown)
        self._style(); self._build(); self._refresh()

    def _style(self):
        style = ttk.Style(self.window); style.theme_use("clam")
        for name, background in (("TFrame",self.COLORS["bg"]),("Card.TFrame",self.COLORS["panel"])):
            style.configure(name, background=background)
        style.configure("TLabel", background=self.COLORS["bg"], foreground=self.COLORS["text"], font=("Segoe UI",10))
        style.configure("Card.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["text"])
        style.configure("Muted.TLabel", foreground=self.COLORS["muted"])
        style.configure("Title.TLabel", font=("Segoe UI Semibold",22))
        style.configure("TButton", padding=(14,9), font=("Segoe UI Semibold",10), background=self.COLORS["card"], foreground=self.COLORS["text"], anchor="center")
        style.map("TButton", background=[("active",self.COLORS["accent"])])
        style.configure("TNotebook", background=self.COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=self.COLORS["card"], foreground=self.COLORS["text"], padding=(16,9))
        style.map("TNotebook.Tab", background=[("selected",self.COLORS["accent"])])
        style.configure("Horizontal.TProgressbar", troughcolor=self.COLORS["card"], background=self.COLORS["accent"])

    def _build(self):
        top = ttk.Frame(self.window, padding=(18,12)); top.pack(fill="x")
        ttk.Label(top, text="TaskGraph", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="v0.4  •  Milestone M2  •  FINAL", style="Muted.TLabel").pack(side="left", padx=14)
        ttk.Button(top, text="Export Report", command=self.export_report).pack(side="right")
        self.accelerator_label = ttk.Label(top, text="Detecting runtime…", style="Muted.TLabel"); self.accelerator_label.pack(side="right", padx=16)
        self.tabs = ttk.Notebook(self.window); self.tabs.pack(fill="both", expand=True, padx=14)
        self.import_page = ttk.Frame(self.tabs, padding=16); self.detect_page = ttk.Frame(self.tabs, padding=16); self.scene_page = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.import_page, text="1  Import Video"); self.tabs.add(self.detect_page, text="2  Detection Workspace"); self.tabs.add(self.scene_page, text="Scene")
        self._build_import(); self._build_detection(); self._build_scene(); self._build_status()

    def _build_import(self):
        card = ttk.Frame(self.import_page, style="Card.TFrame", padding=20); card.pack(fill="both", expand=True)
        ttk.Label(card, text="Import Video", font=("Segoe UI Semibold",20), style="Card.TLabel").pack(anchor="w")
        ttk.Label(card, text="Select a video file, review its properties, then extract a frame gallery.", style="Card.TLabel", foreground=self.COLORS["muted"]).pack(anchor="w", pady=(4,16))
        row = ttk.Frame(card, style="Card.TFrame"); row.pack(fill="x")
        self.video_path = tk.StringVar()
        ttk.Entry(row, textvariable=self.video_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse Video", command=self.browse_video).pack(side="left", padx=(8,0))
        body = ttk.Frame(card, style="Card.TFrame"); body.pack(fill="both", expand=True, pady=16)
        self.video_preview = tk.Canvas(body, bg="#050914", width=760, height=430, highlightthickness=0); self.video_preview.pack(side="left", fill="both", expand=True)
        self.video_preview.create_text(380,215,text="Video preview",fill=self.COLORS["muted"])
        side = ttk.Frame(body, style="Card.TFrame", padding=(20,0)); side.pack(side="left", fill="y")
        self.metadata_labels = {}
        for key in ("File name","Duration","Resolution","FPS"):
            ttk.Label(side,text=key.upper(),style="Card.TLabel",foreground=self.COLORS["muted"]).pack(anchor="w",pady=(8,0))
            label=ttk.Label(side,text="—",style="Card.TLabel",font=("Segoe UI Semibold",12));label.pack(anchor="w");self.metadata_labels[key]=label
        ttk.Label(side,text="EXTRACTION RATE",style="Card.TLabel",foreground=self.COLORS["muted"]).pack(anchor="w",pady=(22,4))
        self.extraction_rate=tk.StringVar(value="1"); ttk.Spinbox(side,from_=0.1,to=30,increment=0.5,textvariable=self.extraction_rate,width=10).pack(anchor="w")
        buttons=ttk.Frame(card,style="Card.TFrame");buttons.pack(fill="x")
        ttk.Button(buttons,text="Extract Frames",command=self.import_video,width=16).pack(side="left")
        ttk.Button(buttons,text="Cancel",command=self.cancel_operation).pack(side="left",padx=8)
        self.import_status=ttk.Label(buttons,text="Choose a video to begin.",style="Card.TLabel");self.import_status.pack(side="left",padx=14)

    def _build_detection(self):
        controls=ttk.Frame(self.detect_page,style="Card.TFrame",padding=10);controls.pack(fill="x")
        ttk.Button(controls,text="Previous",command=lambda:self.show_frame(self.current_frame-1),width=12).pack(side="left")
        ttk.Button(controls,text="Next",command=lambda:self.show_frame(self.current_frame+1),width=12).pack(side="left",padx=6)
        self.frame_counter=ttk.Label(controls,text="Frame 0 / 0",style="Card.TLabel");self.frame_counter.pack(side="left",padx=12)
        ttk.Button(controls,text="Run Model",command=self.run_model,width=14).pack(side="right")
        body=ttk.Frame(self.detect_page);body.pack(fill="both",expand=True,pady=10)
        self.frame_canvas=tk.Canvas(body,bg="#050914",width=940,height=650,highlightthickness=0);self.frame_canvas.pack(side="left",fill="both",expand=True)
        review=ttk.Frame(body,style="Card.TFrame",padding=12);review.pack(side="left",fill="y",padx=(10,0))
        ttk.Label(review,text="User Review",font=("Segoe UI Semibold",16),style="Card.TLabel").pack(anchor="w")
        self.detection_list=tk.Listbox(review,bg=self.COLORS["panel"],fg=self.COLORS["text"],selectbackground=self.COLORS["accent"],relief="flat",width=38,height=24)
        self.detection_list.pack(fill="both",expand=True,pady=10)
        ttk.Button(review,text="Create Object",command=self.create_detection_object).pack(fill="x")
        ttk.Button(review,text="Delete Detection",command=self.delete_detection).pack(fill="x",pady=6)
        ttk.Button(review,text="Move Next",command=lambda:self.show_frame(self.current_frame+1)).pack(fill="x",pady=(0,6))
        ttk.Button(review,text="Object Library",command=self.open_library).pack(fill="x")

    def _build_scene(self):
        self.scene_text=tk.Text(self.scene_page,bg=self.COLORS["panel"],fg=self.COLORS["text"],relief="flat",font=("Cascadia Mono",10),state="disabled")
        self.scene_text.pack(fill="both",expand=True)

    def _build_status(self):
        bar=ttk.Frame(self.window,style="Card.TFrame",padding=(14,8));bar.pack(fill="x")
        self.status_progress=ttk.Progressbar(bar,maximum=100);self.status_progress.grid(row=0,column=0,columnspan=6,sticky="ew",pady=(0,5))
        self.status_labels={}
        keys=("Current Task","Progress","Processed Frames","Current Object","Confidence","Device","Model","FPS","Inference Time","Elapsed","ETA","Memory Usage","Last Completed Operation")
        for position,key in enumerate(keys):
            label=ttk.Label(bar,text=f"{key}: -",style="Card.TLabel",font=("Segoe UI",8),anchor="center")
            label.grid(row=1+position//6,column=position%6,sticky="ew",padx=5)
            bar.columnconfigure(position%6,weight=1)
            self.status_labels[key]=label

    def browse_video(self):
        path=filedialog.askopenfilename(title="Browse Video",filetypes=(("Video files","*.mp4 *.avi *.mov *.mkv *.m4v"),("All files","*.*")))
        if not path:return
        try:
            metadata=self.video.inspect(path);self.video_path.set(path)
            self.metadata_labels["File name"].configure(text=metadata.name);self.metadata_labels["Duration"].configure(text=self._duration(metadata.duration_seconds))
            self.metadata_labels["Resolution"].configure(text=f"{metadata.width} × {metadata.height}");self.metadata_labels["FPS"].configure(text=f"{metadata.fps:.2f}")
            self._preview_file(Path(path));self._operation("Video selected",0,0,metadata.name)
        except Exception as exc:messagebox.showerror("Import Video",str(exc))

    def import_video(self):
        if self.video.metadata is None:messagebox.showwarning("Import Video","Browse for a video first.");return
        try:rate=float(self.extraction_rate.get())
        except ValueError:messagebox.showwarning("Import Video","Extraction rate must be numeric.");return
        self.tabs.select(self.import_page);self._operation("Extract Frames",0,0,"Extraction started")
        self.video.extract_async(rate,self._thread_progress,lambda ok,error:self.window.after(0,self._extraction_done,ok,error))

    def _extraction_done(self,ok,error):
        if ok:
            self._operation("Idle",100,0,f"Extracted {len(self.video.frames)} frames");self.tabs.select(self.detect_page);self.show_frame(0)
        else:self._operation("Idle",0,0,"Extraction cancelled" if error is None else str(error))

    def run_model(self):
        if not self.video.frames:messagebox.showwarning("Run Model","Import and extract a video first.");return
        self._operation("Running YOLO",0,0,"Detection started")
        self.video.detect_async(self._thread_progress,lambda index:self.window.after(0,self._frame_completed,index),lambda ok,error:self.window.after(0,self._detection_done,ok,error))

    def _frame_completed(self,index):
        if index==self.current_frame:self.show_frame(index)

    def _detection_done(self,ok,error):
        if ok:
            failures=len(self.video.errors)
            last=f"Processed {len(self.video.frames)} frames" + (f"; {failures} failed and were logged" if failures else "")
            self._operation("Idle",100,0,last)
        elif error:
            self._operation("Idle",self.progress_value,0,"Detection failed");messagebox.showerror("Structured Detection Error",json.dumps(error,indent=2))
        else:self._operation("Idle",self.progress_value,0,"Detection cancelled")

    def _thread_progress(self,current,total,eta,name):
        self.window.after(0,self._progress,current,total,eta,name)

    def _progress(self,current,total,eta,name):
        percent=100*current/max(1,total);self._operation(self.current_task,percent,eta,f"{name}  ({current}/{total})")
        if self.current_task=="Extract Frames":self.import_status.configure(text=f"{percent:.0f}%  •  ETA {self._duration(eta)}  •  {name}")

    def cancel_operation(self):self.video.cancel();self.last_operation="Cancellation requested"

    def show_frame(self,index):
        if not self.video.frames:return
        self.current_frame=max(0,min(index,len(self.video.frames)-1));self.frame_counter.configure(text=f"Frame {self.current_frame+1} / {len(self.video.frames)}")
        self._render_image(self.frame_canvas,self.video.frames[self.current_frame])
        self.detection_list.delete(0,"end")
        result=self.video.results.get(self.current_frame)
        if result:
            _,vision,scene,annotated,status=result
            self._render_image(self.frame_canvas,annotated)
            self.detection_list.insert("end",f"Frame Number: {self.current_frame+1}")
            self.detection_list.insert("end",f"Status: {status}")
            self.detection_list.insert("end","Detected Objects:")
            for item in vision.objects:self.detection_list.insert("end",f"  {item.properties.get('ai_class') or 'Household object'}  {item.confidence:.2f}")
            self._render_scene(scene)
        elif any(item["frame"]==self.current_frame+1 for item in self.video.errors):
            self.detection_list.insert("end",f"Frame Number: {self.current_frame+1}")
            self.detection_list.insert("end","Status: Processing failed; continued")
        else:
            self.detection_list.insert("end",f"Frame Number: {self.current_frame+1}")
            self.detection_list.insert("end","Status: Pending")

    def create_detection_object(self):
        selection=self.detection_list.curselection();result=self.video.results.get(self.current_frame)
        if not selection or not result:messagebox.showwarning("Create Object","Select a completed detection.");return
        observation,vision,scene,annotated,status=result
        detection_index=selection[0]-3
        if detection_index < 0 or detection_index >= len(vision.objects):messagebox.showwarning("Create Object","Select a detected object row.");return
        item=vision.objects[detection_index]
        dialog=ObjectDetailsDialog(self.window,{"name":item.properties.get("ai_class") or "","category":"household object"})
        if dialog.result is None:return
        region=item.region;rows=[]
        for row in range(region.y,region.y+region.height):
            start=(row*observation.width+region.x)*observation.channels;rows.append(observation.data[start:start+region.width*observation.channels])
        crop={"x":region.x,"y":region.y,"width":region.width,"height":region.height,"channels":observation.channels,"pixel_format":observation.pixel_format,"pixels_hex":b"".join(rows).hex(),"frame_id":observation.observation_id}
        dialog.result["video"]=self.video.metadata.path
        descriptors=tuple((feature.name,tuple(feature.values)) for feature in item.features)
        relationships=tuple(value.relationship_type.value for value in scene.relationships)
        try:response=self.runtime.object_library.create(dialog.result,crop,descriptors,relationships)
        except ValueError as exc:messagebox.showwarning("Create Object",str(exc));return
        self._operation("Idle",100,0,f"Created {dialog.result['name']}")
        if response.status.value=="succeeded":
            self.video.set_review_status(self.current_frame,"Accepted")
            messagebox.showinfo("Create Object","Object saved permanently.")
            self.show_frame(self.current_frame)

    def delete_detection(self):
        selection=self.detection_list.curselection();result=self.video.results.get(self.current_frame)
        if not selection or not result:return
        observation,vision,scene,annotated,status=result
        detection_index=selection[0]-3
        if detection_index < 0 or detection_index >= len(vision.objects):return
        objects=list(vision.objects);objects.pop(detection_index)
        from dataclasses import replace
        self.video.results[self.current_frame]=(observation,replace(vision,objects=tuple(objects)),scene,annotated,"Rejected" if not objects else status)
        if not objects:self.video.set_review_status(self.current_frame,"Rejected")
        self._operation("Idle",100,0,"Detection deleted by user");self.show_frame(self.current_frame)

    def open_library(self):
        self._operation("Open Library",25,0,"Loading objects")
        self.window.after(20,lambda:(ObjectLibraryWindow(self.window,self.runtime.object_library),self._operation("Idle",100,0,"Library opened")))

    def export_report(self,show_dialog=True):
        self._operation("Export",20,0,"Collecting runtime data")
        target=self.root_path/"Assets"/"TaskGraph_Runtime_Report.json";target.parent.mkdir(parents=True,exist_ok=True)
        health=collect_health(self.runtime);timeline=self.runtime.monitor.snapshot();accelerator=accelerator_diagnostics()
        logs=self.runtime.logging.query(LoggingRequest("export-logs","m2-export","desktop-ui"))
        results=[{"frame":index+1,"detections":len(value[1].objects),"scene_objects":len(value[2].objects),"relationships":len(value[2].relationships),"annotated_frame":str(value[3]),"review_status":value[4]} for index,value in sorted(self.video.results.items())]
        payload={"application_version":"TaskGraph v0.4","title":"TaskGraph v0.4 — Robotic Teaching Workstation","milestone":"M2 FINAL","exported_at":datetime.now().isoformat(),"last_five_minutes":self._jsonable(timeline),"engine_health":{name:self._jsonable(item) for name,item in health.items()},"validation":[self._jsonable(item) for item in self.checks],"logs":[self._jsonable(item) for item in logs.snapshot.records],"performance":self.runtime.monitor.rolling_averages(),"frames":[str(path) for path in self.video.frames],"detections":results,"scene":self._jsonable(results[-1] if results else {}),"relationships":[self._jsonable(item) for item in (self.video.results[max(self.video.results)][2].relationships if self.video.results else ())],"objects":self._jsonable(self.runtime.object_library.list()),"recognition":{"review_library_lookup":False,"automatic_merge":False},"memory":{"permanent_library_path":str(self.root_path/"Assets"/"ObjectLibrary"/"objects.json")},"errors":[item for item in timeline if item["status"]=="failed"],"warnings":[item for item in timeline if item["status"] not in ("succeeded","failed")],"gpu":accelerator,"cpu":self.runtime.monitor.rolling_averages().get("cpu_percent"),"ram":self.runtime.monitor.rolling_averages().get("ram_bytes"),"timeline":self._jsonable(timeline)}
        payload["title"]="TaskGraph"
        target.write_text(json.dumps(payload,indent=2),encoding="utf-8");self._operation("Idle",100,0,f"Exported {target.name}")
        if show_dialog:messagebox.showinfo("Export Report",f"Exported to\n{target}")

    def run_validation(self,show_dialog=True):
        self._operation("Validation",10,0,"Running M2 validation");self.checks=validate_runtime(self.runtime,"ui-m2-validation");self._operation("Idle",100,0,"Validation complete")
        if show_dialog:messagebox.showinfo("M2 Validation","PASS" if validation_passed(self.checks) else "FAIL")

    def run_demo(self):self.tabs.select(self.import_page)

    def _preview_file(self,path):
        try:
            import cv2
            capture=cv2.VideoCapture(str(path));ok,image=capture.read();capture.release()
            if ok:
                temporary=self.root_path/"Workspace"/".preview.png";temporary.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(temporary),image);self._render_image(self.video_preview,temporary)
        except Exception:pass

    def _render_image(self,canvas,path):
        try:
            image=tk.PhotoImage(file=str(path));cw,ch=max(1,canvas.winfo_width()),max(1,canvas.winfo_height())
            factor=max(1,max((image.width()+cw-1)//cw,(image.height()+ch-1)//ch));image=image.subsample(factor,factor)
            canvas.delete("all");canvas.create_image(cw/2,ch/2,image=image);canvas._image=image
        except Exception as exc:canvas.delete("all");canvas.create_text(20,20,text=str(exc),anchor="nw",fill=self.COLORS["red"])

    def _draw_boxes(self,vision):
        image=getattr(self.frame_canvas,"_image",None)
        if not image:return
        result=self.video.results[self.current_frame];observation=result[0];cw,ch=max(1,self.frame_canvas.winfo_width()),max(1,self.frame_canvas.winfo_height())
        scale=min(image.width()/observation.width,image.height()/observation.height);ox=(cw-image.width())/2;oy=(ch-image.height())/2
        for item in vision.objects:
            r=item.region;self.frame_canvas.create_rectangle(ox+r.x*scale,oy+r.y*scale,ox+(r.x+r.width)*scale,oy+(r.y+r.height)*scale,outline=self.COLORS["green"],width=2)
            self.frame_canvas.create_text(ox+r.x*scale,oy+r.y*scale,text=item.properties.get("ai_class") or "Object",anchor="sw",fill=self.COLORS["green"])

    def _render_scene(self,scene):
        lines=[f"Generation: {scene.scene_id}",f"Health: {scene.diagnostics.tracking_health}",f"Object count: {len(scene.objects)}",""]
        lines += [f"{item.scene_object_id}  age={item.update_count}  motion={item.motion_state.value}" for item in scene.objects]
        lines += ["",f"Relationships: {[item.relationship_type.value for item in scene.relationships]}"]
        self.scene_text.configure(state="normal");self.scene_text.delete("1.0","end");self.scene_text.insert("end","\n".join(lines));self.scene_text.configure(state="disabled")

    def _operation(self,task,progress,eta,last):
        self.current_task,self.progress_value,self.eta_value,self.last_operation=task,progress,eta,last
        if hasattr(self,"status_progress"):self.status_progress["value"]=progress

    def _refresh(self):
        if self._closed:return
        diagnostics=accelerator_diagnostics();samples=self.runtime.monitor.snapshot();sample=next((item for item in reversed(samples) if item["action"]=="sample"),{"details":{}})["details"];averages=self.runtime.monitor.rolling_averages()
        self.accelerator_label.configure(text=f"PyTorch {diagnostics.get('torch_version') or 'Unavailable'}  •  CUDA {diagnostics.get('cuda_available')}  •  {diagnostics.get('gpu_name') or 'CPU'}  •  Torch/YOLO {self.runtime.perception.detector_status().get('device','CPU')}")
        detector=self.runtime.perception.detector_status()
        processed=len(self.video.results)+len(self.video.errors);total=len(self.video.frames)
        values={"Current Task":self.current_task,"Progress":f"{self.progress_value:.0f}%","Processed Frames":f"{processed} / {total}","Current Object":self.video.current_object or "-","Confidence":"-" if self.video.current_confidence is None else f"{self.video.current_confidence:.2f}","Device":detector.get("device") or diagnostics.get("gpu_name") or "CPU","Model":detector.get("current") or "-","FPS":f"{averages.get('inference_fps',0):.2f}","Inference Time":f"{detector.get('inference_ms') or 0:.1f} ms","Elapsed":self._duration(monotonic()-self._started),"ETA":self._duration(self.eta_value),"Memory Usage":f"{sample.get('process_memory_bytes',0)/1073741824:.2f} GB","Last Completed Operation":self.last_operation}
        for key,value in values.items():self.status_labels[key].configure(text=f"{key}: {value}")
        self.window.after(1000,self._refresh)

    def shutdown(self):
        if self._closed:return
        self._closed=True;self.video.cancel();results=shutdown_runtime(self.runtime);failed=[name for name,value in results.items() if value.status.value!="succeeded"]
        if failed:messagebox.showerror("Shutdown",f"Shutdown failures: {', '.join(failed)}")
        self.window.destroy()

    def run(self):self.window.mainloop()

    @staticmethod
    def _duration(seconds):
        seconds=max(0,int(seconds or 0));return f"{seconds//60:02d}:{seconds%60:02d}"

    @staticmethod
    def _jsonable(value):
        if is_dataclass(value):return {field.name:TaskGraphApp._jsonable(getattr(value,field.name)) for field in fields(value)}
        if hasattr(value,"items"):return {str(key):TaskGraphApp._jsonable(item) for key,item in value.items()}
        if isinstance(value,(tuple,list,set,frozenset)):return [TaskGraphApp._jsonable(item) for item in value]
        if isinstance(value,bytes):return value.hex()
        if hasattr(value,"value"):return value.value
        return value
