import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import fnmatch
from datetime import datetime, date, timedelta

# generate_preview function remains unchanged
def generate_preview(profile_config):
    try:
        source_dir = profile_config.get('source_path', '')
        patterns = [p.strip() for p in profile_config.get('file_format', '').split(',') if p.strip()]
        action = profile_config.get('action', 'copy')
        destination_path = profile_config.get('destination_path', '')
        
        age_config = profile_config.get('file_age', {})
        if isinstance(age_config, dict):
            age_value = age_config.get('value', 0)
            age_unit = age_config.get('unit', 'Days')
        else: 
            age_value = 0; age_unit = 'Days'

        date_limit = None
        if age_unit != "No Limit":
            days_to_subtract = age_value
            if age_unit == "Months": days_to_subtract *= 30
            elif age_unit == "Years": days_to_subtract *= 365
            date_limit = date.today() - timedelta(days=days_to_subtract)
        
        if not os.path.isdir(source_dir): raise FileNotFoundError(f"Source folder not found: {source_dir}")

        found_files = []
        with os.scandir(source_dir) as entries:
            for entry in entries:
                if not entry.is_file(): continue
                matched_pattern = next((p for p in patterns if fnmatch.fnmatch(entry.name, p)), None)
                if not matched_pattern: continue
                mod_date = date.fromtimestamp(entry.stat().st_mtime)
                if date_limit is not None and mod_date < date_limit: continue
                
                file_info = {
                    "file": entry.path, "rule": matched_pattern, "action": "Move" if action == 'move' else "copy",
                    "destination": destination_path, "new_name": entry.name,
                    "size": f"{entry.stat().st_size / 1024:.2f} KB" if entry.stat().st_size > 1024 else f"{entry.stat().st_size} B"
                }
                found_files.append(file_info)
        return found_files, None
    except Exception as e:
        return [], str(e)

class PreviewWindow(tk.Toplevel):
    # This class remains unchanged
    def __init__(self, parent, preview_data):
        super().__init__(parent)
        self.title("Profile Execution Preview"); self.geometry("900x500"); self.transient(parent); self.grab_set()
        cols = ("File", "Rule", "Action", "Destination", "New Name", "Size")
        self.tree = ttk.Treeview(self, columns=cols, show='headings')
        for col in cols: self.tree.heading(col, text=col); self.tree.column(col, width=150, anchor='w')
        self.tree.column("File", width=250); self.tree.column("Rule", width=100)
        self.tree.column("Action", width=80); self.tree.column("Size", width=80, anchor='e')
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew'); vsb.grid(row=0, column=1, sticky='ns'); hsb.grid(row=1, column=0, sticky='ew')
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)
        self.populate_data(preview_data)

    def populate_data(self, data):
        for item in data: self.tree.insert("", "end", values=list(item.values()))


class ProfileEditor(tk.Toplevel):
    def __init__(self, parent, profile=None, existing_names=None, icon_path=None):
        super().__init__(parent)
        self.transient(parent); self.parent = parent
        self.profile = profile if profile else {}
        self.existing_names = existing_names if existing_names else []
        self.result = None

        self.title("Create / Edit Profile"); self.geometry("600x480"); self.resizable(False, False); self.grab_set()
        
        # --- CORRECTION 1: Set window icon ---
        if icon_path:
            try:
                self.iconbitmap(icon_path)
            except tk.TclError:
                pass # Icon not found, do nothing
        
        self._setup_vars(); self._setup_ui(); self._load_profile_data()

        # --- CORRECTION 2: Center window relative to parent ---
        self.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        self_width = self.winfo_width()
        self_height = self.winfo_height()
        x = parent_x + (parent_width // 2) - (self_width // 2)
        y = parent_y + (parent_height // 2) - (self_height // 2)
        self.geometry(f"+{x}+{y}")

    def _setup_vars(self):
        # ... (method remains unchanged) ...
        self.profile_name = tk.StringVar(); self.action = tk.StringVar(value='copy')
        self.source_path = tk.StringVar(); self.destination_path = tk.StringVar()
        self.db_path = tk.StringVar(); self.log_path = tk.StringVar()
        self.file_format = tk.StringVar()
        self.file_age_value = tk.IntVar(value=0)
        self.file_age_unit = tk.StringVar(value="Days")
        self.scan_interval_value = tk.IntVar(value=5)
        self.scan_interval_unit = tk.StringVar(value="s")
        self.enabled = tk.BooleanVar(value=True)

    def _browse(self, var, dialog_type='folder'):
        # ... (method remains unchanged) ...
        path = ""
        if dialog_type == 'folder': path = filedialog.askdirectory()
        elif dialog_type == 'db_file': path = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("Database files", "*.db"), ("All files", "*.*")])
        elif dialog_type == 'log_file': path = filedialog.asksaveasfilename(defaultextension=".log", filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")])
        if path: var.set(path)

    def _load_profile_data(self):
        # ... (method remains unchanged) ...
        if not self.profile: return
        self.profile_name.set(self.profile.get('name', ''))
        self.action.set(self.profile.get('action', 'copy'))
        self.source_path.set(self.profile.get('source_path', '')); self.destination_path.set(self.profile.get('destination_path', ''))
        self.db_path.set(self.profile.get('db_path', '')); self.log_path.set(self.profile.get('log_path', ''))
        self.file_format.set(self.profile.get('file_format', ''))
        self.enabled.set(self.profile.get('enabled', False))
        
        age_config = self.profile.get('file_age', {'value': 0, 'unit': 'Days'})
        if isinstance(age_config, dict):
            self.file_age_value.set(age_config.get('value', 0)); self.file_age_unit.set(age_config.get('unit', 'Days'))
        else:
            self.file_age_value.set(0); self.file_age_unit.set('Days')

        interval_config = self.profile.get('scan_interval', {'value': 5, 'unit': 's'})
        if isinstance(interval_config, dict):
            self.scan_interval_value.set(interval_config.get('value', 5)); self.scan_interval_unit.set(interval_config.get('unit', 's'))
        else:
            self.scan_interval_value.set(interval_config or 5); self.scan_interval_unit.set('s')
    
    def _get_current_config(self):
        # ... (method remains unchanged) ...
        return {'name': self.profile_name.get().strip(), 'action': self.action.get(), 'source_path': self.source_path.get(),
            'destination_path': self.destination_path.get(), 'db_path': self.db_path.get(), 'log_path': self.log_path.get(),
            'file_format': self.file_format.get(), 'file_age': {'value': self.file_age_value.get(), 'unit': self.file_age_unit.get()},
            'scan_interval': {'value': self.scan_interval_value.get(), 'unit': self.scan_interval_unit.get()}, 'enabled': self.enabled.get()}

    def _on_generate_preview(self):
        # ... (method remains unchanged) ...
        current_config = self._get_current_config()
        found_files, error = generate_preview(current_config)
        if error: messagebox.showerror("Preview Error", f"Could not generate preview:\n{error}", parent=self); return
        if not found_files: messagebox.showinfo("Preview", "No files found with the current rules.", parent=self); return
        PreviewWindow(self, found_files)

    def _on_save(self):
        # ... (method remains unchanged) ...
        current_config = self._get_current_config()
        name = current_config['name']
        if not name: messagebox.showerror("Error", "Profile name cannot be empty.", parent=self); return
        current_name = self.profile.get('name')
        if name != current_name and name in self.existing_names:
            messagebox.showerror("Error", "A profile with this name already exists.", parent=self); return
        self.result = current_config
        self.destroy()

    def _setup_ui(self):
        main_frame = ttk.Frame(self, padding=15); main_frame.pack(expand=True, fill=tk.BOTH)

        top_frame = ttk.Frame(main_frame); top_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(top_frame, text="Profile Name:").pack(side=tk.LEFT, anchor='w')
        ttk.Entry(top_frame, textvariable=self.profile_name, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Checkbutton(top_frame, text="Active", variable=self.enabled).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(top_frame, text="Move", variable=self.action, onvalue='move', offvalue='copy').pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(top_frame, text="Copy", variable=self.action, onvalue='copy', offvalue='move').pack(side=tk.LEFT)
        
        paths_frame = ttk.LabelFrame(main_frame, text="Folder Configuration", padding=10)
        paths_frame.pack(fill=tk.X, pady=(0, 20)); paths_frame.columnconfigure(1, weight=1)
        path_configs = [("Source Folder (Input):", self.source_path, 'folder'), ("Destination Folder (Output):", self.destination_path, 'folder'),
            ("Database File (Queue):", self.db_path, 'db_file'), ("Profile Log File:", self.log_path, 'log_file')]
        for i, (label, var, dialog_type) in enumerate(path_configs):
            ttk.Label(paths_frame, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=5)
            ttk.Entry(paths_frame, textvariable=var).grid(row=i, column=1, sticky='ew', padx=5)
            ttk.Button(paths_frame, text="Browse...", command=lambda v=var, dt=dialog_type: self._browse(v, dt)).grid(row=i, column=2, padx=5)
            
        rules_frame = ttk.Frame(main_frame); rules_frame.pack(fill=tk.BOTH, expand=True); rules_frame.columnconfigure(1, weight=1)
        ttk.Label(rules_frame, text="File Format (patterns separated by comma):").grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 5))
        ttk.Entry(rules_frame, textvariable=self.file_format).grid(row=1, column=0, columnspan=4, sticky='ew', pady=(0, 20))
        ttk.Label(rules_frame, text="File age:").grid(row=2, column=0, sticky='w', pady=5)
        ttk.Spinbox(rules_frame, from_=0, to=999, textvariable=self.file_age_value, width=5).grid(row=2, column=1, sticky='w')
        age_combo = ttk.Combobox(rules_frame, textvariable=self.file_age_unit, values=["Days", "Months", "Years", "No Limit"], state='readonly', width=10)
        age_combo.grid(row=2, column=2, sticky='w', padx=5)
        ttk.Label(rules_frame, text="Scan interval:").grid(row=3, column=0, sticky='w', pady=5)
        ttk.Spinbox(rules_frame, from_=1, to=999, textvariable=self.scan_interval_value, width=5).grid(row=3, column=1, sticky='w')
        interval_combo = ttk.Combobox(rules_frame, textvariable=self.scan_interval_unit, values=["s", "min", "hr"], state='readonly', width=10)
        interval_combo.grid(row=3, column=2, sticky='w', padx=5)
        
        # --- CORRECTION 3: Center buttons ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, pady=(10, 0)) # Pack frame without fill
        ttk.Button(button_frame, text="Generate Preview", command=self._on_generate_preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save", command=self._on_save, style="Accent.TButton").pack(side=tk.LEFT, padx=5)