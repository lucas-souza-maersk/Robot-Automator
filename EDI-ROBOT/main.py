import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import queue
import logging
import os
import sys
import json
from threading import Thread
from PIL import Image
import pystray
import psutil

import config_manager
import logger_setup
import data_manager
from profile_editor import ProfileEditor

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class CustomClosingDialog(tk.Toplevel):
    """A custom dialog to ask the user whether to minimize or exit."""
    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.transient(parent)
        self.parent = parent
        self.title("Close Application")
        self.resizable(False, False)
        self.grab_set()

        width = 350
        height = 140
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.deiconify()

        try:
            self.icon_path = resource_path("apm.ico")
            self.iconbitmap(self.icon_path)
        except tk.TclError:
            self.icon_path = None
            logging.warning("apm.ico not found.")

        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(expand=True, fill=tk.BOTH)

        label = ttk.Label(main_frame, text="What would you like to do?", font=("Segoe UI", 11, "bold"), anchor="center", justify="center")
        label.pack(fill=tk.X, pady=(0, 15))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(expand=True)

        btn_minimize = ttk.Button(button_frame, text="Minimize to Tray", command=self.minimize_to_tray, style="Accent.TButton")
        btn_minimize.grid(row=0, column=0, padx=(0, 10))

        btn_exit = ttk.Button(button_frame, text="Exit Application", command=self.exit_app)
        btn_exit.grid(row=0, column=1)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def minimize_to_tray(self):
        self.parent.hide_to_tray()
        self.destroy()

    def exit_app(self):
        self.destroy()
        self.parent.quit_application()

class MainApplication(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.profiles = config_manager.load_profiles()
        self.active_profile_name = tk.StringVar()

        self.title("Robo Automator - Control Panel")
        self.geometry("950x750")
        self.minsize(900, 700)
        
        try:
            self.icon_path = resource_path("apm.ico")
            self.iconbitmap(self.icon_path)
        except tk.TclError:
            self.icon_path = None
            logging.warning("apm.ico not found.")

        self.log_queue = queue.Queue()
        logger_setup.setup_main_logger(self.log_queue)

        self.setup_ui()
        
        self.update_profile_dropdown()
        self.after(100, self.process_log_queue)
        self.after(3000, self.update_dashboard_loop)
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing) 
        self.setup_system_tray()
        logging.info("Configuration Application Initialized.")

    def on_closing(self):
        CustomClosingDialog(self)

    def check_service_is_running(self):
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if proc.info['name'] in ['RoboService.exe', 'run_service.exe']:
                    return True
                if 'python' in proc.info['name'].lower() and proc.info['cmdline'] and 'run_service.py' in proc.info['cmdline'][-1]:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    def hide_to_tray(self):
        self.withdraw()

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_application(self):
        if hasattr(self, 'icon'): self.icon.stop()
        self.destroy()

    def setup_system_tray(self):
        try:
            if not self.icon_path: return
            icon_image = Image.open(self.icon_path)
            menu = (pystray.MenuItem('Show Panel', self.show_window, default=True),
                    pystray.MenuItem('Quit Panel', self.quit_application))
            self.icon = pystray.Icon("RoboAutomator", icon_image, "Robo Automator", menu)
            tray_thread = Thread(target=self.icon.run, daemon=True)
            tray_thread.start()
        except Exception as e:
            logging.error(f"System tray icon could not be initialized: {e}")

    def setup_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(pady=10, padx=10, expand=True, fill=tk.BOTH)
        self.dashboard_frame = ttk.Frame(self.notebook, padding="10")
        self.logs_frame = ttk.Frame(self.notebook, padding="10")
        self.settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.dashboard_frame, text='Dashboard')
        self.notebook.add(self.logs_frame, text='Real-time Logs')
        self.notebook.add(self.settings_frame, text='Profile Settings')
        self.setup_dashboard()
        self.setup_logs()
        self.setup_settings()

    def update_profile_dropdown(self):
        profile_names = list(self.profiles.keys())
        self.profile_selector['values'] = profile_names
        if profile_names:
            if self.active_profile_name.get() not in profile_names:
                self.active_profile_name.set(profile_names[0])
            self.on_profile_select()
        else:
            self.active_profile_name.set("")
            self.on_profile_select()

    def on_profile_select(self, event=None):
        profile_name = self.active_profile_name.get()
        if profile_name:
            profile_config = self.profiles[profile_name]
            db_path = profile_config.get('settings', {}).get('db_path')
            if db_path:
                data_manager.initialize_database(db_path)
            else:
                logging.warning(f"Profile '{profile_name}' has no db_path configured.")
        self.update_dashboard_display()

    def update_dashboard_loop(self):
        if self.winfo_viewable():
            self.update_dashboard_display()
        self.after(5000, self.update_dashboard_loop)

    def update_dashboard_display(self):
        service_running = self.check_service_is_running()
        if service_running:
            self.main_service_status_var.set("AUTOMATION ENGINE: ACTIVE")
            self.main_service_status_label.config(foreground="green")
        else:
            self.main_service_status_var.set("AUTOMATION ENGINE: INACTIVE (Service process not detected)")
            self.main_service_status_label.config(foreground="red")

        profile_name = self.active_profile_name.get()
        if not profile_name or profile_name not in self.profiles:
            self.profile_status_var.set("No Profile Selected")
            self.profile_status_label.config(foreground="orange")
            for var in [self.queue_count_var, self.sent_count_var, self.failed_count_var, self.duplicate_count_var]:
                var.set(0)
            for i in self.queue_tree.get_children(): self.queue_tree.delete(i)
            return

        profile_config = self.profiles[profile_name]
        profile_is_enabled = profile_config.get('enabled', False)
        db_path = profile_config.get('settings', {}).get('db_path')

        if service_running and profile_is_enabled:
            self.profile_status_var.set("ACTIVE (Running via Service)")
            self.profile_status_label.config(foreground="green")
        elif not profile_is_enabled:
            self.profile_status_var.set("INACTIVE (Disabled in profile settings)")
            self.profile_status_label.config(foreground="gray")
        else:
            self.profile_status_var.set("PENDING (Engine service is stopped)")
            self.profile_status_label.config(foreground="orange")

        if db_path:
            stats = data_manager.get_queue_stats(db_path)
            self.queue_count_var.set(stats.get('pending', 0))
            self.sent_count_var.set(stats.get('sent', 0))
            self.failed_count_var.set(stats.get('failed', 0))
            self.duplicate_count_var.set(stats.get('duplicate', 0))

            if not self.queue_tree.selection():
                for i in self.queue_tree.get_children(): self.queue_tree.delete(i)
                items = data_manager.get_all_queue_items(db_path)
                for item in items:
                    (item_id, status, retries, file_path, file_hash, added, processed, original_path) = item
                    
                    filename = os.path.basename(file_path or original_path or "N/A")
                    hash_display = (file_hash[:10] + '...') if file_hash else "N/A"
                    display_item = (item_id, status, retries, filename, hash_display, added, processed or "N/A")
                    self.queue_tree.insert("", "end", values=display_item)
            
    def setup_dashboard(self):
        main_status_frame = ttk.Frame(self.dashboard_frame, padding=(0, 0, 0, 10))
        main_status_frame.pack(fill='x')
        self.main_service_status_var = tk.StringVar()
        self.main_service_status_label = ttk.Label(main_status_frame, textvariable=self.main_service_status_var, font=("Segoe UI", 10, "bold"), anchor='center')
        self.main_service_status_label.pack(fill='x')
        top_frame = ttk.Frame(self.dashboard_frame)
        top_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(top_frame, text="Monitor Profile:").pack(side='left', padx=(0, 5))
        self.profile_selector = ttk.Combobox(top_frame, textvariable=self.active_profile_name, state='readonly', width=40)
        self.profile_selector.pack(side='left', fill='x', expand=True)
        self.profile_selector.bind("<<ComboboxSelected>>", self.on_profile_select)

        status_panel = ttk.LabelFrame(self.dashboard_frame, text="Selected Profile Status", padding="10")
        status_panel.pack(fill="x", expand=False, pady=(10,0))
        status_panel.columnconfigure(1, weight=1)
        status_font = ("Segoe UI", 10); status_value_font = ("Segoe UI", 10, "bold")
        self.profile_status_var = tk.StringVar()
        self.queue_count_var = tk.IntVar(); self.sent_count_var = tk.IntVar()
        self.failed_count_var = tk.IntVar(); self.duplicate_count_var = tk.IntVar()
        
        ttk.Label(status_panel, text="Profile Status:", font=status_font).grid(row=0, column=0, sticky="w")
        self.profile_status_label = ttk.Label(status_panel, textvariable=self.profile_status_var, font=status_value_font)
        self.profile_status_label.grid(row=0, column=1, sticky="w", padx=5, columnspan=3)
        ttk.Label(status_panel, text="Files in Queue:", font=status_font).grid(row=1, column=0, sticky="w", pady=(10,0))
        ttk.Label(status_panel, textvariable=self.queue_count_var, font=status_value_font).grid(row=1, column=1, sticky="w", padx=5, pady=(10,0))
        ttk.Label(status_panel, text="Sent (Total):", font=status_font).grid(row=2, column=0, sticky="w")
        ttk.Label(status_panel, textvariable=self.sent_count_var, font=status_value_font).grid(row=2, column=1, sticky="w", padx=5)
        ttk.Label(status_panel, text="Failed (Total):", font=status_font).grid(row=1, column=2, sticky="w", padx=20, pady=(10,0))
        ttk.Label(status_panel, textvariable=self.failed_count_var, font=status_value_font).grid(row=1, column=3, sticky="w", padx=5, pady=(10,0))
        ttk.Label(status_panel, text="Duplicates (Total):", font=status_font).grid(row=2, column=2, sticky="w", padx=20)
        ttk.Label(status_panel, textvariable=self.duplicate_count_var, font=status_value_font).grid(row=2, column=3, sticky="w", padx=5)

        queue_panel = ttk.LabelFrame(self.dashboard_frame, text="Queue Monitor", padding="10")
        queue_panel.pack(fill="both", expand=True, pady=10)
        tree_frame = ttk.Frame(queue_panel); tree_frame.pack(fill='both', expand=True)
        cols = ("ID", "Status", "Retries", "File Name", "Hash", "Added", "Processed")
        self.queue_tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        for col in cols: self.queue_tree.heading(col, text=col); self.queue_tree.column(col, width=100, anchor='w')
        self.queue_tree.column("File Name", width=250); self.queue_tree.column("Hash", width=120)
        self.queue_tree.column("Added", width=140); self.queue_tree.column("Processed", width=140)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.queue_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.queue_tree.xview)
        self.queue_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.queue_tree.grid(row=0, column=0, sticky='nsew'); vsb.grid(row=0, column=1, sticky='ns'); hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1); tree_frame.grid_columnconfigure(0, weight=1)
        button_frame = ttk.Frame(queue_panel); button_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(button_frame, text="Refresh Queue", command=self.update_dashboard_display).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Retry Selected Failed", command=self.retry_selected_items).pack(side="left", padx=5)

    def setup_logs(self):
        self.log_text_area = scrolledtext.ScrolledText(self.logs_frame, wrap=tk.WORD, state='disabled', font=("Consolas", 9))
        self.log_text_area.pack(expand=True, fill="both", pady=5)
        clear_button = ttk.Button(self.logs_frame, text="Clear Log View", command=self._clear_log_display)
        clear_button.pack(fill='x')

    def _clear_log_display(self):
        if messagebox.askyesno("Clear Logs", "Are you sure you want to clear the log view? This does not affect the saved log file."):
            self.log_text_area.configure(state='normal'); self.log_text_area.delete('1.0', tk.END); self.log_text_area.configure(state='disabled')
            logging.info("Log view cleared by user.")

    def setup_settings(self):
            settings_container = ttk.Frame(self.settings_frame); settings_container.pack(expand=True, fill='both', pady=20)
            left_frame = ttk.Frame(settings_container); left_frame.pack(side='left', fill='both', expand=True, padx=(0,10))
            right_frame = ttk.Frame(settings_container); right_frame.pack(side='left', fill='y')
            
            ttk.Label(left_frame, text="Existing Profiles:").pack(anchor='w')
            self.profile_listbox = tk.Listbox(left_frame, height=15); self.profile_listbox.pack(fill='both', expand=True)
            self.update_profile_listbox()

            ttk.Button(right_frame, text="Create New Profile", command=self.create_profile).pack(fill='x', pady=5)
            ttk.Button(right_frame, text="Edit Profile", command=self.edit_profile).pack(fill='x', pady=5)
            ttk.Button(right_frame, text="Delete Profile", command=self.delete_profile).pack(fill='x', pady=5)
            
            about_frame = ttk.LabelFrame(right_frame, text="About", padding=10)
            about_frame.pack(fill='x', pady=(20, 5), side='bottom') 
            ttk.Label(
                about_frame, 
                text="Robo Automator V2.0\nDeveloped by Lucas Melo\nFor APM Terminals Pecém", 
                justify=tk.CENTER
            ).pack()

    def update_profile_listbox(self):
        self.profile_listbox.delete(0, tk.END)
        for name in sorted(self.profiles.keys()):
            is_enabled = self.profiles[name].get('enabled', False)
            status_tag = '[ACTIVE]' if is_enabled else '[INACTIVE]'
            display_name = f"{name} {status_tag}"
            self.profile_listbox.insert(tk.END, display_name)

    def _get_selected_profile_name(self):
        selected_indices = self.profile_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select a profile.", parent=self)
            return None
        selected_text = self.profile_listbox.get(selected_indices[0])

        if selected_text.endswith(' [ACTIVE]'):
            return selected_text[:-9]
        elif selected_text.endswith(' [INACTIVE]'):
            return selected_text[:-11]
        else:
            return selected_text

    def create_profile(self):
        editor = ProfileEditor(self, existing_names=list(self.profiles.keys()), icon_path=self.icon_path)
        self.wait_window(editor)
        if editor.result:
            profile_name = editor.result['name']
            self.profiles[profile_name] = editor.result
            config_manager.save_profiles(self.profiles)
            self.update_profile_listbox(); self.update_profile_dropdown()
            messagebox.showinfo("Success", f"Profile '{profile_name}' created successfully.")

    def edit_profile(self):
        old_name = self._get_selected_profile_name()
        if not old_name: return
        profile_data = self.profiles[old_name]
        existing_names = [name for name in self.profiles if name != old_name]
        editor = ProfileEditor(self, profile=profile_data, existing_names=existing_names, icon_path=self.icon_path)
        self.wait_window(editor)
        if editor.result:
            new_data = editor.result
            if old_name != new_data['name']: del self.profiles[old_name]
            self.profiles[new_data['name']] = new_data
            config_manager.save_profiles(self.profiles)
            self.update_profile_listbox(); self.update_profile_dropdown()
            messagebox.showinfo("Success", f"Profile '{new_data['name']}' updated successfully.")

    def delete_profile(self):
        profile_name = self._get_selected_profile_name()
        if not profile_name: return
        if messagebox.askyesno("Confirm", f"Are you sure you want to delete the profile '{profile_name}'?", parent=self):
            del self.profiles[profile_name]
            config_manager.save_profiles(self.profiles)
            self.update_profile_listbox(); self.update_profile_dropdown()
            messagebox.showinfo("Success", f"Profile '{profile_name}' deleted.")
    
    def retry_selected_items(self):
        profile_name = self.active_profile_name.get()
        if not profile_name: return
        
        db_path = self.profiles[profile_name].get('settings', {}).get('db_path')
        if not db_path:
            messagebox.showerror("Error", "No database path configured for this profile.", parent=self)
            return

        selected_items = self.queue_tree.selection()
        if not selected_items:
            messagebox.showinfo("Information", "No items selected.", parent=self)
            return
            
        item_ids_to_retry = [self.queue_tree.item(i, 'values')[0] for i in selected_items if self.queue_tree.item(i, 'values')[1] == 'failed']
        
        if not item_ids_to_retry:
            messagebox.showinfo("Information", "No 'failed' items were selected for retry.", parent=self)
            return

        data_manager.reset_failed_items(db_path, item_ids_to_retry)
        messagebox.showinfo("Success", f"{len(item_ids_to_retry)} item(s) have been re-queued for processing.")
        self.update_dashboard_display()

    def process_log_queue(self):
        try:
            while True:
                record = self.log_queue.get_nowait()
                msg = record.getMessage()
                if not self.log_text_area.winfo_exists(): break
                self.log_text_area.configure(state='normal')
                self.log_text_area.insert(tk.END, msg + '\n')
                self.log_text_area.configure(state='disabled')
                self.log_text_area.yview(tk.END)
        except queue.Empty: pass
        finally:
            if self.winfo_exists():
                self.after(100, self.process_log_queue)

if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = MainApplication()
    app.mainloop()