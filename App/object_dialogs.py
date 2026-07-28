"""Object creation and library windows for user-owned perception memory."""
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk


FIELDS = ("name", "category", "description", "material", "color", "aliases", "tags", "notes")


class ObjectDetailsDialog:
    def __init__(self, parent, initial=None):
        self.result = None
        window = self.window = tk.Toplevel(parent); window.title("Create Object"); window.transient(parent); window.grab_set()
        self.values = {}
        for row, name in enumerate(FIELDS):
            ttk.Label(window, text=name.replace("_", " ").title()).grid(row=row, column=0, sticky="w", padx=12, pady=5)
            entry = ttk.Entry(window, width=42); entry.grid(row=row, column=1, padx=12, pady=5); self.values[name] = entry
            if initial and name in initial: entry.insert(0, ", ".join(initial[name]) if isinstance(initial[name], tuple) else str(initial[name]))
        self.values["name"].focus_set()
        ttk.Label(window, text="Created Date").grid(row=len(FIELDS), column=0, sticky="w", padx=12, pady=5)
        ttk.Label(window, text=datetime.now().isoformat(timespec="seconds")).grid(row=len(FIELDS), column=1, sticky="w", padx=12, pady=5)
        buttons = ttk.Frame(window); buttons.grid(row=len(FIELDS) + 1, column=0, columnspan=2, pady=12)
        ttk.Button(buttons, text="Save", command=self._accept).pack(side="left", padx=5)
        ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side="left", padx=5)
        parent.wait_window(window)

    def _accept(self):
        values = {name: entry.get() for name, entry in self.values.items()}
        if not values["name"].strip(): messagebox.showwarning("Object", "Object Name is required.", parent=self.window); return
        values["created"] = datetime.now().isoformat(timespec="seconds"); self.result = values; self.window.destroy()


class ObjectLibraryWindow:
    def __init__(self, parent, library):
        self.library = library
        self.window = tk.Toplevel(parent); self.window.title("TaskGraph Object Library"); self.window.geometry("1050x680")
        controls = ttk.Frame(self.window, padding=10); controls.pack(fill="x")
        self.search = tk.StringVar(); ttk.Entry(controls, textvariable=self.search, width=35).pack(side="left"); ttk.Button(controls, text="Search", command=self.refresh).pack(side="left", padx=6)
        self.sort = tk.StringVar(value="Name"); ttk.Combobox(controls, textvariable=self.sort, values=("Name", "Category", "Times Seen", "Last Updated"), state="readonly", width=14).pack(side="left"); ttk.Button(controls, text="Sort", command=self.refresh).pack(side="left", padx=6)
        self.filter = tk.StringVar(value="All"); ttk.Combobox(controls, textvariable=self.filter, values=("All", "Household object"), state="readonly", width=18).pack(side="left", padx=6)
        columns = ("name", "category", "description", "times_seen", "confidence", "updated")
        self.tree = ttk.Treeview(self.window, columns=columns, show="headings")
        for column in columns: self.tree.heading(column, text=column.replace("_", " ").title()); self.tree.column(column, width=150)
        self.tree.pack(fill="both", expand=True, padx=10)
        footer = ttk.Frame(self.window, padding=10); footer.pack(fill="x"); ttk.Button(footer, text="Details", command=self.details).pack(side="left"); ttk.Button(footer, text="Edit", command=self.edit).pack(side="left", padx=6); ttk.Button(footer, text="Delete", command=self.delete).pack(side="left", padx=6)
        self.refresh()

    def refresh(self):
        values = list(self.library.list()); query = self.search.get().lower().strip()
        if query: values = [item for item in values if query in str(item.get("name", "")).lower() or query in str(item.get("category", "")).lower()]
        category = self.filter.get()
        if category != "All": values = [item for item in values if str(item.get("category", "")).casefold() == category.casefold()]
        keys = {"Name":"name","Category":"category","Times Seen":"times_seen","Last Updated":"updated"}
        key = keys[self.sort.get()]; values.sort(key=lambda item: str(item.get(key, "")))
        for row in self.tree.get_children(): self.tree.delete(row)
        for item in values:
            scores = next((descriptor[1] for descriptor in item.get("descriptors", ()) if descriptor[0] == "scores"), ())
            confidence = scores[-1] if scores else 0
            confidence = float(item.get("average_confidence", confidence))
            self.tree.insert("", "end", iid=item["object_id"], values=(item["name"], item["category"], item.get("description",""), item.get("times_seen",1), f"{confidence:.0%}", item.get("updated",item.get("created",""))))

    def _selected(self):
        selection = self.tree.selection(); return selection[0] if selection else None

    def details(self):
        identity = self._selected()
        if identity:
            item = next(value for value in self.library.list() if value["object_id"] == identity)
            messagebox.showinfo(item["name"], "\n".join(f"{key}: {value}" for key, value in item.items() if key != "crop"), parent=self.window)

    def delete(self):
        identity = self._selected()
        if identity and messagebox.askyesno("Confirm Delete", "Permanently delete this object from the Object Library?", parent=self.window): self.library.delete(identity); self.refresh()

    def edit(self):
        identity = self._selected()
        if not identity: return
        item = next(value for value in self.library.list() if value["object_id"] == identity); dialog = ObjectDetailsDialog(self.window, item)
        if dialog.result: self.library.update(identity, dialog.result); self.refresh()
