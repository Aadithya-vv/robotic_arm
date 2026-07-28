from __future__ import annotations
import tkinter as tk
from tkinter import messagebox,ttk

class Splash:
    def __init__(self,version="v1.1.1",root_path=None):
        self.root=tk.Tk();self.root.title("TaskGraph");self.root.geometry("590x450");self.root.configure(bg="#0b1020");self.root.resizable(False,False)
        if root_path:
            icon=root_path/"Assets"/"Branding"/"taskgraph.ico"
            if icon.is_file():self.root.iconbitmap(str(icon))
        tk.Label(self.root,text="TASKGRAPH",font=("Segoe UI",26,"bold"),fg="#edf4ff",bg="#0b1020").pack(pady=(28,2));tk.Label(self.root,text=version,fg="#7fa9f8",bg="#0b1020").pack()
        self.status=tk.StringVar(value="Initializing Runtime");tk.Label(self.root,textvariable=self.status,fg="#dbeafe",bg="#0b1020",font=("Segoe UI",11,"bold")).pack(pady=(26,10));self.bar=ttk.Progressbar(self.root,length=460,mode="determinate",maximum=100);self.bar.pack();self.detail=tk.StringVar();tk.Label(self.root,textvariable=self.detail,fg="#94a3b8",bg="#0b1020").pack(pady=10)
        panel=tk.Frame(self.root,bg="#111a2e",padx=18,pady=12);panel.pack(fill="x",padx=48,pady=8);self.fields={name:tk.StringVar(value="Checking…") for name in ("GPU","CUDA","Backend","Frontend","Browser","Logs")}
        for row,(name,value) in enumerate(self.fields.items()):tk.Label(panel,text=name,fg="#718096",bg="#111a2e",anchor="w").grid(row=row,column=0,sticky="w",pady=2);tk.Label(panel,textvariable=value,fg="#d4e3fa",bg="#111a2e",anchor="e").grid(row=row,column=1,sticky="e",pady=2)
        panel.grid_columnconfigure(1,weight=1);self.root.update()
    def update(self,text:str,value:int,detail:str=""):self.status.set(text);self.bar["value"]=value;self.detail.set(detail);self.root.update()
    def telemetry(self,**values):
        for name,value in values.items():
            if name in self.fields:self.fields[name].set(str(value))
        self.root.update_idletasks()
    def pump(self):self.root.update_idletasks();self.root.update()
    def error(self,title:str,reason:str,solution:str):messagebox.showerror(title,f"{reason}\n\nSolution\n{solution}",parent=self.root)
    def confirm_shutdown(self)->bool:return messagebox.askyesno("TaskGraph is still running","Shutdown frontend and backend?",parent=self.root)
    def hide(self):self.root.withdraw()
    def show(self):self.root.deiconify();self.root.update()
    def destroy(self):self.root.destroy()
