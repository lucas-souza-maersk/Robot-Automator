import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import stat
import fnmatch
from datetime import date, timedelta, datetime
import keyring
import pysftp


class SftpBrowser(tk.Toplevel):
    """A Toplevel window to browse a remote SFTP server's filesystem."""
    def __init__(self, parent, conn_details, icon_path=None):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("SFTP Browser")
        self.geometry("600x400")

        self.conn_details = conn_details
        self.current_path = tk.StringVar(value=conn_details.get('remote_path', '/'))
        self.result = None

        if icon_path:
            try:
                self.iconbitmap(icon_path)
            except tk.TclError:
                pass
        
        self._setup_ui()
        self._connect_and_populate()
        

    def _setup_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        nav_frame = ttk.Frame(main_frame)
        nav_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        nav_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(nav_frame, text="Up", command=self._navigate_up).pack(side="left")
        ttk.Entry(nav_frame, textvariable=self.current_path, state="readonly").pack(side="left", fill="x", expand=True, padx=5)

        self.tree = ttk.Treeview(main_frame, columns=("size", "modified"), show="tree headings")
        
        self.tree.heading("#0", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("modified", text="Modified")

        self.tree.column("#0", width=250, stretch=tk.YES)
        self.tree.column("size", width=100, anchor="e", stretch=tk.NO)
        self.tree.column("modified", width=150, anchor="w", stretch=tk.NO)
        
        self.tree.grid(row=1, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frame, text="Select Current Path", command=self._on_select, style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

        self.tree.bind("<Double-1>", self._on_item_double_click)

    def _connect_and_populate(self):
        host = self.conn_details.get('host')
        username = self.conn_details.get('username')
        password = self.conn_details.get('password')
        port = self.conn_details.get('port', 22)
        
        if not all([host, username, password, port]):
            messagebox.showerror("Connection Error", "Missing connection details.", parent=self)
            self.destroy()
            return
            
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None 

        try:
            with pysftp.Connection(host, username=username, password=password, port=port, cnopts=cnopts) as sftp:
                self._populate_tree(sftp, self.current_path.get())
        except Exception as e:
            messagebox.showerror("SFTP Error", f"Could not connect or list directory:\n{e}", parent=self)
            self.destroy()

    def _populate_tree(self, sftp, path):
        self.tree.delete(*self.tree.get_children())
        try:
            sftp.cwd(path)
            self.current_path.set(sftp.pwd)
            items = sorted(sftp.listdir_attr(), key=lambda attr: (not stat.S_ISDIR(attr.st_mode), attr.filename.lower()))

            for attr in items:
                item_type = "folder" if stat.S_ISDIR(attr.st_mode) else "file"
                size = f"{attr.st_size / 1024:.2f} KB" if item_type == "file" else ""
                mod_time = datetime.fromtimestamp(attr.st_mtime).strftime('%Y-%m-%d %H:%M')
                
                prefix = "📁 " if item_type == "folder" else "📄 "
                self.tree.insert("", "end", text=f"{prefix}{attr.filename}", values=(size, mod_time), iid=attr.filename)

        except Exception as e:
            messagebox.showwarning("Navigation Error", f"Could not access path: {path}\n{e}", parent=self)

    def _on_item_double_click(self, event):
        item_id = self.tree.focus()
        if not item_id: return
        
        item = self.tree.item(item_id)
        filename = item['text'].lstrip("📁📄 ")
        
        if "📁" in item['text']:
            new_path = os.path.join(self.current_path.get(), filename).replace("\\", "/")
            self.current_path.set(new_path)
            self._connect_and_populate()


    def _navigate_up(self):
        current = self.current_path.get()
        if current and current != '/':
            parent = os.path.dirname(current).replace("\\", "/")
            self.current_path.set(parent)
            self._connect_and_populate()

    def _on_select(self):
        self.result = self.current_path.get()
        self.destroy()

class PreviewWindow(tk.Toplevel):
    """Displays a preview of files that will be processed."""
    def __init__(self, parent, preview_data, icon_path=None):
        super().__init__(parent)
        self.title("Profile Execution Preview")
        self.geometry("900x500")
        self.transient(parent)
        self.grab_set()

        if icon_path:
            try:
                self.iconbitmap(icon_path)
            except tk.TclError:
                pass

        cols = ("File", "Size", "Action", "Rule", "Source", "Destination")
        self.tree = ttk.Treeview(self, columns=cols, show='headings')
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150, anchor='w')

        self.tree.column("File", width=250)
        self.tree.column("Size", width=80, anchor='e')
        self.tree.column("Action", width=80)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.populate_data(preview_data)
        self._center_window()

    def populate_data(self, data):
        for item in data:
            self.tree.insert("", "end", values=list(item.values()))
    
    def _center_window(self):
        self.update_idletasks()
        parent_x = self.winfo_toplevel().winfo_x()
        parent_y = self.winfo_toplevel().winfo_y()
        parent_width = self.winfo_toplevel().winfo_width()
        parent_height = self.winfo_toplevel().winfo_height()
        self_width = self.winfo_width()
        self_height = self.winfo_height()
        x = parent_x + (parent_width // 2) - (self_width // 2)
        y = parent_y + (parent_height // 2) - (self_height // 2)
        self.geometry(f"+{x}+{y}")

class RemoteEndpointsSetup(tk.Toplevel):
    """A tabbed window for configuring remote source and/or destination details."""
    def __init__(self, parent, profile_data, icon_path=None):
        super().__init__(parent)
        self.transient(parent)
        self.parent = parent
        self.result = profile_data
        self.icon_path = icon_path
        self.source_type = profile_data.get('source', {}).get('type')
        self.dest_type = profile_data.get('destination', {}).get('type')

        self.title("Remote Endpoints Setup")
        self.grab_set()

        if icon_path:
            try:
                self.iconbitmap(icon_path)
            except tk.TclError:
                pass

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)


        self.tabs = {}
        if self.source_type != 'local':
            self._create_tab('source', f"Source ({self.source_type.upper()})")
        if self.dest_type != 'local':
            self._create_tab('destination', f"Destination ({self.dest_type.upper()})")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=(0, 10))
        ttk.Button(btn_frame, text="Save Connections", command=self._on_save, style="Accent.TButton").pack()
        
        self.update_idletasks()
        self.minsize(self.winfo_width(), self.winfo_height())
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        self_width = self.winfo_width()
        self_height = self.winfo_height()
        x = parent_x + (parent_width // 2) - (self_width // 2)
        y = parent_y + (parent_height // 2) - (self_height // 2)
        self.geometry(f"+{x}+{y}")

    def _create_tab(self, key, title):
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text=title)
        
        host = tk.StringVar(value=self.result.get(key, {}).get('host', ''))
        port = tk.IntVar(value=self.result.get(key, {}).get('port', 22))
        username = tk.StringVar(value=self.result.get(key, {}).get('username', ''))
        password = tk.StringVar() 
        remote_path = tk.StringVar(value=self.result.get(key, {}).get('remote_path', '/'))
        
        self.tabs[key] = {'host': host, 'port': port, 'username': username, 'password': password, 'remote_path': remote_path}
        
        conn_frame = ttk.LabelFrame(tab, text="Server Connection", padding=10)
        conn_frame.pack(fill='x')
        ttk.Label(conn_frame, text="Host:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(conn_frame, textvariable=host, width=40).grid(row=0, column=1, sticky='ew', padx=5)
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, sticky='w', padx=5)
        ttk.Entry(conn_frame, textvariable=port, width=6).grid(row=0, column=3, sticky='w', padx=5)
        
        ttk.Label(conn_frame, text="Username:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(conn_frame, textvariable=username).grid(row=1, column=1, columnspan=3, sticky='ew', padx=5)
        
        ttk.Label(conn_frame, text="Password:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(conn_frame, textvariable=password, show='*').grid(row=2, column=1, columnspan=3, sticky='ew', padx=5)
        ttk.Label(conn_frame, text="(Leave empty to keep existing password)", font=("Segoe UI", 8)).grid(row=3, column=1, columnspan=3, sticky='w', padx=5)

        path_frame = ttk.LabelFrame(tab, text="Remote Path", padding=10)
        path_frame.pack(fill='x', pady=10)
        ttk.Label(path_frame, text="Path:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(path_frame, textvariable=remote_path, width=40).grid(row=0, column=1, sticky='ew', padx=5)
        ttk.Button(path_frame, text="Browse...", command=lambda k=key: self._browse_sftp(k)).grid(row=0, column=2, padx=5)
        
        conn_frame.columnconfigure(1, weight=1)
        path_frame.columnconfigure(1, weight=1)

    def _browse_sftp(self, key):
        tab_vars = self.tabs[key]
        host = tab_vars['host'].get()
        username = tab_vars['username'].get()
        password = tab_vars['password'].get()

        if not password:
            try:
                password = keyring.get_password(f"robot_automator::{host}", username)
            except Exception as e:
                messagebox.showwarning("Keyring Warning", f"Could not get password from keyring:\n{e}", parent=self)

        if not password:
            messagebox.showerror("Error", "Please enter a password to browse the SFTP server.", parent=self)
            return

        conn_details = {
            'host': host,
            'port': tab_vars['port'].get(),
            'username': username,
            'password': password,
            'remote_path': tab_vars['remote_path'].get()
        }

        browser = SftpBrowser(self, conn_details, icon_path=self.icon_path)
        self.wait_window(browser)

        if browser.result is not None:
            tab_vars['remote_path'].set(browser.result)

    def _on_save(self):
        for key, vars_dict in self.tabs.items():
            host = vars_dict['host'].get().strip()
            username = vars_dict['username'].get().strip()
            
            if not host or not username:
                messagebox.showerror("Error", f"Host and Username are required for '{key}'.", parent=self)
                return

            self.result[key] = self.result.get(key, {})
            self.result[key].update({
                'host': host,
                'port': vars_dict['port'].get(),
                'username': username,
                'remote_path': vars_dict['remote_path'].get(),
            })

            password = vars_dict['password'].get()
            if password:
                try:
                    service_name = f"robot_automator::{host}"
                    keyring.set_password(service_name, username, password)
                    messagebox.showinfo("Success", f"Password for {username}@{host} saved securely.", parent=self.parent)
                except Exception as e:
                    messagebox.showerror("Keyring Error", f"Could not save password for {key}:\n{e}", parent=self)
                    return
        self.destroy()


class ProfileEditor(tk.Toplevel):
    def __init__(self, parent, profile=None, existing_names=None, icon_path=None):
        super().__init__(parent)
        self.transient(parent)
        self.parent = parent
        self.profile = profile if profile else {}
        self.existing_names = existing_names if existing_names else []
        self.result = None
        
        self.title("Create / Edit Profile")
        self.resizable(False, False)
        self.geometry("600x850") 
        self.grab_set()
        if icon_path:
            try: self.iconbitmap(icon_path)
            except tk.Toplevel: pass
        
        self._setup_vars()
        self._setup_ui()
        self._load_profile_data()
        self._update_ui_for_types()
        self._toggle_alert_frame()
        self._toggle_backup_frame()
        self._center_window()

    def _setup_vars(self):
        self.profile_name = tk.StringVar()
        self.enabled = tk.BooleanVar(value=True)
        self.action = tk.StringVar(value='copy')
        self.source_type = tk.StringVar(value='local')
        self.dest_type = tk.StringVar(value='local')
        self.source_local_path = tk.StringVar()
        self.dest_local_path = tk.StringVar()
        self.db_path = tk.StringVar()
        self.log_path = tk.StringVar()
        self.file_format = tk.StringVar(value='*.*')
        self.file_age_value = tk.IntVar(value=0)
        self.file_age_unit = tk.StringVar(value="Days")
        self.scan_interval_value = tk.IntVar(value=5)
        self.scan_interval_unit = tk.StringVar(value="s")
        self.remote_config = {}

        self.backup_enabled = tk.BooleanVar(value=False)
        self.backup_path = tk.StringVar()

        self.alert_enabled = tk.BooleanVar(value=False)
        self.alert_webhook_url = tk.StringVar()
        self.alert_level = tk.StringVar(value="Apenas Crítico")

    def _setup_ui(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(expand=True, fill=tk.BOTH)
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(top_frame, text="Profile Name:").pack(side=tk.LEFT)
        ttk.Entry(top_frame, textvariable=self.profile_name, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Checkbutton(top_frame, text="Active", variable=self.enabled).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(top_frame, text="Move", variable=self.action, value='move').pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(top_frame, text="Copy", variable=self.action, value='copy').pack(side=tk.LEFT)
        flow_frame = ttk.LabelFrame(main_frame, text="Transfer Flow (Source -> Destination)", padding=10)
        flow_frame.pack(fill=tk.X, pady=10)
        conn_types = ["local", "SFTP", "FTP", "SCP"]
        ttk.Label(flow_frame, text="Source Connection Type:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        ttk.Combobox(flow_frame, textvariable=self.source_type, values=conn_types, state='readonly').grid(row=0, column=1, sticky='ew', padx=5)
        ttk.Label(flow_frame, text="Destination Connection Type:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        ttk.Combobox(flow_frame, textvariable=self.dest_type, values=conn_types, state='readonly').grid(row=1, column=1, sticky='ew', padx=5)
        ttk.Label(flow_frame, text="Remote Endpoints Setup:").grid(row=0, column=2, rowspan=2, sticky='w', padx=(20, 5))
        self.setup_conn_button = ttk.Button(flow_frame, text="Setup Connection(s)", command=self._open_remote_setup)
        self.setup_conn_button.grid(row=0, column=3, rowspan=2, padx=5)
        flow_frame.columnconfigure(1, weight=1)
        self.source_local_frame = ttk.LabelFrame(main_frame, text="Source (Input) Configuration: LOCAL", padding=10)
        self.dest_local_frame = ttk.LabelFrame(main_frame, text="Destination (Output) Configuration: LOCAL", padding=10)
        self.source_remote_frame = ttk.LabelFrame(main_frame, text="Source (Input) Configuration: REMOTE", padding=10)
        self.dest_remote_frame = ttk.LabelFrame(main_frame, text="Destination (Output) Configuration: REMOTE", padding=10)
        self.source_local_frame.pack(fill=tk.X, pady=5)
        self.dest_local_frame.pack(fill=tk.X, pady=5)
        self.source_remote_frame.pack(fill=tk.X, pady=5)
        self.dest_remote_frame.pack(fill=tk.X, pady=5)
        self._create_path_entry(self.source_local_frame, "Local Path (Input):", self.source_local_path)
        self._create_path_entry(self.dest_local_frame, "Local Path (Output):", self.dest_local_path)
        ttk.Label(self.source_remote_frame, text="Configure connection details via 'Setup Connection(s)' button.").pack()
        ttk.Label(self.dest_remote_frame, text="Configure connection details via 'Setup Connection(s)' button.").pack()
        
        control_frame = ttk.LabelFrame(main_frame, text="Control Files", padding=10)
        control_frame.pack(fill=tk.X, pady=10)
        self._create_path_entry(control_frame, "Database File (Queue):", self.db_path, is_file=True, ext=".db")
        self._create_path_entry(control_frame, "Profile Log File:", self.log_path, is_file=True, ext=".log", pady=(5,0))
        
        # Backup Frame
        backup_frame = ttk.LabelFrame(main_frame, text="Backup Settings", padding=10)
        backup_frame.pack(fill=tk.X, pady=10)
        backup_frame.columnconfigure(1, weight=1)
        
        ttk.Checkbutton(backup_frame, text="Enable Local Backup (Copy successful files)", variable=self.backup_enabled, command=self._toggle_backup_frame).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0,5))
        
        self.backup_widgets_frame = ttk.Frame(backup_frame)
        self.backup_widgets_frame.grid(row=1, column=0, columnspan=3, sticky='ew')
        self.backup_widgets_frame.columnconfigure(1, weight=1)
        self._create_path_entry(self.backup_widgets_frame, "Backup Folder:", self.backup_path)

        settings_frame = ttk.LabelFrame(main_frame, text="File Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=10)
        ttk.Label(settings_frame, text="File Format (patterns separated by comma):").grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 5))
        ttk.Entry(settings_frame, textvariable=self.file_format).grid(row=1, column=0, columnspan=4, sticky='ew', pady=(0, 10))
        ttk.Label(settings_frame, text="File Age:").grid(row=2, column=0, sticky='w', pady=5)
        ttk.Spinbox(settings_frame, from_=0, to=999, textvariable=self.file_age_value, width=5).grid(row=2, column=1, sticky='w')
        age_combo = ttk.Combobox(settings_frame, textvariable=self.file_age_unit, values=["Days", "Months", "Years", "No Limit"], state='readonly', width=10)
        age_combo.grid(row=2, column=2, sticky='w', padx=5)
        ttk.Label(settings_frame, text="Scan Interval:").grid(row=3, column=0, sticky='w', pady=5)
        ttk.Spinbox(settings_frame, from_=1, to=999, textvariable=self.scan_interval_value, width=5).grid(row=3, column=1, sticky='w')
        interval_combo = ttk.Combobox(settings_frame, textvariable=self.scan_interval_unit, values=["s", "min", "hr"], state='readonly', width=10)
        interval_combo.grid(row=3, column=2, sticky='w', padx=5)
        
        alert_frame = ttk.LabelFrame(main_frame, text="Alertas (MS Teams)", padding=10)
        alert_frame.pack(fill=tk.X, pady=10)
        alert_frame.columnconfigure(1, weight=1)

        ttk.Checkbutton(alert_frame, text="Habilitar Alertas no Teams", variable=self.alert_enabled, command=self._toggle_alert_frame).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0,5))
        
        self.alert_widgets_frame = ttk.Frame(alert_frame)
        self.alert_widgets_frame.grid(row=1, column=0, columnspan=2, sticky='ew')
        self.alert_widgets_frame.columnconfigure(1, weight=1)

        ttk.Label(self.alert_widgets_frame, text="Webhook URL:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(self.alert_widgets_frame, textvariable=self.alert_webhook_url, width=40).grid(row=0, column=1, sticky='ew', padx=5)

        ttk.Label(self.alert_widgets_frame, text="Nível de Alerta:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        alert_level_combo = ttk.Combobox(self.alert_widgets_frame, textvariable=self.alert_level, values=["Apenas Crítico", "Erros & Avisos", "Info (Sucessos)"], state='readonly', width=20)
        alert_level_combo.grid(row=1, column=1, sticky='w', padx=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, pady=(10, 0))
        ttk.Button(button_frame, text="Generate Preview", command=self._on_generate_preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save", command=self._on_save, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        self.source_type.trace_add("write", self._update_ui_for_types)
        self.dest_type.trace_add("write", self._update_ui_for_types)

    def _toggle_alert_frame(self, *args):
        if self.alert_enabled.get():
            self.alert_widgets_frame.grid(row=1, column=0, columnspan=2, sticky='ew')
        else:
            self.alert_widgets_frame.grid_forget()

    def _toggle_backup_frame(self, *args):
        if self.backup_enabled.get():
            self.backup_widgets_frame.grid(row=1, column=0, columnspan=3, sticky='ew')
        else:
            self.backup_widgets_frame.grid_forget()

    def _create_path_entry(self, parent, label_text, var, is_file=False, ext="", pady=0):
        parent.columnconfigure(1, weight=1)
        next_row = parent.grid_size()[1] 
        ttk.Label(parent, text=label_text).grid(row=next_row, column=0, sticky='w', padx=5, pady=pady)
        ttk.Entry(parent, textvariable=var).grid(row=next_row, column=1, sticky='ew', padx=5)
        ttk.Button(parent, text="Browse...", command=lambda: self._browse(var, is_file, ext)).grid(row=next_row, column=2, padx=5)

    def _center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        x = parent_x + (parent_w // 2) - (w // 2)
        y = parent_y + (parent_h // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')

    def _update_ui_for_types(self, *args):
        is_source_local = self.source_type.get() == 'local'
        is_dest_local = self.dest_type.get() == 'local'
        if is_source_local:
            self.source_local_frame.pack(fill=tk.X, pady=5)
            self.source_remote_frame.pack_forget()
        else:
            self.source_remote_frame.pack(fill=tk.X, pady=5)
            self.source_local_frame.pack_forget()
        if is_dest_local:
            self.dest_local_frame.pack(fill=tk.X, pady=5)
            self.dest_remote_frame.pack_forget()
        else:
            self.dest_remote_frame.pack(fill=tk.X, pady=5)
            self.dest_local_frame.pack_forget()
        self.setup_conn_button.config(state='normal' if not (is_source_local and is_dest_local) else 'disabled')

    def _browse(self, var, is_file=False, ext=""):
        if is_file:
            path = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[(f"{ext.upper()} files", f"*{ext}"), ("All files", "*.*")])
        else:
            path = filedialog.askdirectory()
        if path: var.set(path)

    def _open_remote_setup(self):
        data_to_pass = {
            'source': self.remote_config.get('source', {'type': self.source_type.get()}),
            'destination': self.remote_config.get('destination', {'type': self.dest_type.get()}),
        }
        setup_win = RemoteEndpointsSetup(self, data_to_pass, icon_path=self.parent.icon_path)
        self.wait_window(setup_win)
        self.remote_config = setup_win.result

    def _load_profile_data(self):
        if not self.profile: return
        self.profile_name.set(self.profile.get('name', ''))
        self.enabled.set(self.profile.get('enabled', True))
        self.action.set(self.profile.get('action', 'copy'))
        source_cfg = self.profile.get('source', {})
        dest_cfg = self.profile.get('destination', {})
        settings = self.profile.get('settings', {})
        self.source_type.set(source_cfg.get('type', 'local'))
        self.dest_type.set(dest_cfg.get('type', 'local'))
        if self.source_type.get() == 'local':
            self.source_local_path.set(source_cfg.get('path', ''))
        if self.dest_type.get() == 'local':
            self.dest_local_path.set(dest_cfg.get('path', ''))
        self.db_path.set(settings.get('db_path', ''))
        self.log_path.set(settings.get('log_path', ''))
        self.file_format.set(settings.get('file_format', '*.*'))
        age = settings.get('file_age', {'value': 0, 'unit': 'Days'})
        self.file_age_value.set(age.get('value', 0))
        self.file_age_unit.set(age.get('unit', 'Days'))
        interval = settings.get('scan_interval', {'value': 5, 'unit': 's'})
        self.scan_interval_value.set(interval.get('value', 5))
        self.scan_interval_unit.set(interval.get('unit', 's'))
        
        backup_cfg = settings.get('backup', {})
        self.backup_enabled.set(backup_cfg.get('enabled', False))
        self.backup_path.set(backup_cfg.get('path', ''))

        alert_cfg = settings.get('alerting', {})
        self.alert_enabled.set(alert_cfg.get('enabled', False))
        self.alert_webhook_url.set(alert_cfg.get('webhook_url', ''))
        self.alert_level.set(alert_cfg.get('level', 'Apenas Crítico'))
        
        self.remote_config = {'source': source_cfg, 'destination': dest_cfg}

    def _on_save(self):
        name = self.profile_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Profile name cannot be empty.", parent=self)
            return
        current_name = self.profile.get('name')
        if name != current_name and name in self.existing_names:
            messagebox.showerror("Error", "A profile with this name already exists.", parent=self)
            return
        
        if self.alert_enabled.get() and not self.alert_webhook_url.get().strip():
             messagebox.showerror("Validation Error", "Teams Webhook URL is required when alerts are enabled.", parent=self)
             return
        
        if self.backup_enabled.get() and not self.backup_path.get().strip():
            messagebox.showerror("Validation Error", "Backup folder path is required if backup is enabled.", parent=self)
            return

        source = {'type': self.source_type.get()}
        if source['type'] == 'local':
            if not self.source_local_path.get():
                messagebox.showerror("Validation Error", "Source Path is required for local source.", parent=self)
                return
            source['path'] = self.source_local_path.get()
        else:
            if not self.remote_config.get('source', {}).get('host'):
                messagebox.showerror("Validation Error", "Source connection must be configured.", parent=self)
                return
            source.update(self.remote_config.get('source', {}))
        destination = {'type': self.dest_type.get()}
        if destination['type'] == 'local':
            if not self.dest_local_path.get():
                messagebox.showerror("Validation Error", "Destination Path is required for local destination.", parent=self)
                return
            destination['path'] = self.dest_local_path.get()
        else:
            if not self.remote_config.get('destination', {}).get('host'):
                messagebox.showerror("Validation Error", "Destination connection must be configured.", parent=self)
                return
            destination.update(self.remote_config.get('destination', {}))
        self.result = {
            'name': name,
            'enabled': self.enabled.get(),
            'action': self.action.get(),
            'source': source,
            'destination': destination,
            'settings': {
                'db_path': self.db_path.get(),
                'log_path': self.log_path.get(),
                'file_format': self.file_format.get(),
                'file_age': {'value': self.file_age_value.get(), 'unit': self.file_age_unit.get()},
                'scan_interval': {'value': self.scan_interval_value.get(), 'unit': self.scan_interval_unit.get()},
                'backup': {
                    'enabled': self.backup_enabled.get(),
                    'path': self.backup_path.get().strip()
                },
                'alerting': {
                    'enabled': self.alert_enabled.get(),
                    'webhook_url': self.alert_webhook_url.get().strip(),
                    'level': self.alert_level.get()
                }
            }
        }
        self.destroy()

    def _on_generate_preview(self):
        current_config = self._get_current_config_for_preview()
        source_type = current_config['source']['type']
        found_files, error = [], None
        try:
            if source_type == 'local':
                found_files, error = self._preview_local(current_config)
            elif source_type == 'SFTP':
                found_files, error = self._preview_sftp(current_config)
            else:
                error = f"Preview for '{source_type}' is not yet implemented."
        except Exception as e:
            error = f"An unexpected error occurred during preview:\n{e}"
        if error:
            messagebox.showerror("Preview Error", error, parent=self)
            return
        if not found_files:
            messagebox.showinfo("Preview", "No files found matching the current criteria.", parent=self)
            return
        PreviewWindow(self, found_files, icon_path=self.parent.icon_path)

    def _get_current_config_for_preview(self):
        source = {'type': self.source_type.get()}
        if source['type'] == 'local':
            source['path'] = self.source_local_path.get()
        else:
            source.update(self.remote_config.get('source', {}))
        destination = {'type': self.dest_type.get()}
        if destination['type'] == 'local':
            destination['path'] = self.dest_local_path.get()
        else:
             destination.update(self.remote_config.get('destination', {}))
        return {
            'action': self.action.get(),
            'source': source,
            'destination': destination,
            'settings': {
                'file_format': self.file_format.get(),
                'file_age': {'value': self.file_age_value.get(), 'unit': self.file_age_unit.get()}
            }
        }

    def _get_date_limit(self, config):
        age_config = config['settings']['file_age']
        age_value = age_config.get('value', 0)
        age_unit = age_config.get('unit', 'Days')
        if age_unit == "No Limit": return None
        days_to_subtract = age_value
        if age_unit == "Months": days_to_subtract *= 30
        elif age_unit == "Years": days_to_subtract *= 365
        return date.today() - timedelta(days=days_to_subtract)
        
    def _preview_local(self, config):
        source_dir = config['source']['path']
        patterns = [p.strip() for p in config['settings']['file_format'].split(',') if p.strip()]
        date_limit = self._get_date_limit(config)
        if not os.path.isdir(source_dir):
            return [], f"Source folder not found: {source_dir}"
        found_files = []
        with os.scandir(source_dir) as entries:
            for entry in entries:
                if not entry.is_file(): continue
                if not any(fnmatch.fnmatch(entry.name, p) for p in patterns): continue
                mod_date = date.fromtimestamp(entry.stat().st_mtime)
                if date_limit and mod_date < date_limit: continue
                size_kb = entry.stat().st_size / 1024
                file_info = { "file": entry.name, "size": f"{size_kb:.2f} KB", "action": config['action'],
                    "rule": next((p for p in patterns if fnmatch.fnmatch(entry.name, p)), ""),
                    "source": source_dir, "destination": config['destination']['path'] }
                found_files.append(file_info)
        return found_files, None

    def _preview_sftp(self, config):
        source_cfg = config['source']
        host, username = source_cfg.get('host'), source_cfg.get('username')
        if not host or not username:
            return [], "SFTP Host and Username are not configured."
        try:
            password = keyring.get_password(f"robot_automator::{host}", username)
            if not password:
                return [], f"Password for {username}@{host} not found in secure storage. Please configure the connection and save the password."
        except Exception as e:
            return [], f"Could not retrieve password from keyring: {e}"
        patterns = [p.strip() for p in config['settings']['file_format'].split(',') if p.strip()]
        date_limit = self._get_date_limit(config)
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        found_files = []
        try:
            with pysftp.Connection(host, username=username, password=password, port=source_cfg.get('port', 22), cnopts=cnopts) as sftp:
                sftp.cwd(source_cfg.get('remote_path', '/'))
                for attr in sftp.listdir_attr():
                    if not sftp.isfile(attr.filename): continue
                    if not any(fnmatch.fnmatch(attr.filename, p) for p in patterns): continue
                    mod_date = date.fromtimestamp(attr.st_mtime)
                    if date_limit and mod_date < date_limit: continue
                    size_kb = attr.st_size / 1024
                    dest_path_str = ""
                    if config['destination']['type'] == 'local':
                        dest_path_str = config['destination']['path']
                    else:
                        dest_path_str = f"sftp://{config['destination'].get('host')}{config['destination'].get('remote_path')}"
                    file_info = { "file": attr.filename, "size": f"{size_kb:.2f} KB", "action": config['action'],
                        "rule": next((p for p in patterns if fnmatch.fnmatch(attr.filename, p)), ""),
                        "source": f"sftp://{host}{sftp.pwd}", "destination": dest_path_str }
                    found_files.append(file_info)
            return found_files, None
        except Exception as e:
            return [], f"Failed to connect or list files on SFTP server:\n{e}"