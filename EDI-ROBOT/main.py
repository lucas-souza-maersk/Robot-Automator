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
from services import ServiceManager
from profile_editor import ProfileEditor

def resource_path(relative_path):
    """ Obtém o caminho absoluto para o recurso, funciona para dev e para PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class MainApplication(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.profiles = config_manager.load_profiles()
        self.running_services = {}
        self.active_profile_name = tk.StringVar()

        self.title("Automatizador de Tarefas - APM Terminals")
        self.geometry("950x750")
        self.minsize(900, 700)
        
        try:
            self.icon_path = resource_path("apm.ico")
            self.iconbitmap(self.icon_path)
        except tk.TclError:
            self.icon_path = None
            logging.warning("apm.ico não encontrado.")

        self.log_queue = queue.Queue()
        logger_setup.setup_main_logger(self.log_queue)

        self.setup_ui()
        
        self.update_profile_dropdown()
        self.after(100, self.process_log_queue)
        self.after(2000, self.update_dashboard_loop)
        
        self.protocol("WM_DELETE_WINDOW", self.esconder_para_bandeja)
        self.setup_bandeja_sistema()
        logging.info("Aplicação de Configuração inicializada.")

    def check_service_is_running(self):
        """Verifica se o processo do serviço 'RoboEdiService.exe' está em execução."""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == 'RoboEdiService.exe':
                return True
        return False

    def esconder_para_bandeja(self):
        self.withdraw()

    def mostrar_janela(self):
        self.deiconify()

    def sair_aplicacao(self):
        if messagebox.askokcancel("Sair", "Tem a certeza que deseja fechar a aplicação? Isto não irá parar o serviço do Windows."):
            if hasattr(self, 'icon'): self.icon.stop()
            self.destroy()

    def setup_bandeja_sistema(self):
        try:
            if not self.icon_path: return
            icon_image = Image.open(self.icon_path)
            menu = (pystray.MenuItem('Mostrar Painel', self.mostrar_janela, default=True),
                    pystray.MenuItem('Sair do Painel', self.sair_aplicacao))
            self.icon = pystray.Icon("Automatizador", icon_image, "Automatizador de Tarefas", menu)
            tray_thread = Thread(target=self.icon.run, daemon=True)
            tray_thread.start()
        except Exception as e:
            logging.error(f"Ícone da bandeja do sistema não iniciado: {e}")

    def setup_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(pady=10, padx=10, expand=True, fill=tk.BOTH)

        self.dashboard_frame = ttk.Frame(self.notebook, padding="10")
        self.logs_frame = ttk.Frame(self.notebook, padding="10")
        self.settings_frame = ttk.Frame(self.notebook, padding="10")

        self.notebook.add(self.dashboard_frame, text='Dashboard')
        self.notebook.add(self.logs_frame, text='Logs em Tempo Real')
        self.notebook.add(self.settings_frame, text='Configurações de Perfis')
        
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
            data_manager.initialize_database(profile_config['db_path'])
        self.update_dashboard_display()

    def start_selected_profile(self):
        profile_name = self.active_profile_name.get()
        if not profile_name: return
        
        if not (profile_name in self.running_services and self.running_services[profile_name].is_running()):
            profile_config = self.profiles[profile_name]
            service_manager = ServiceManager(profile_config, self.log_queue)
            self.running_services[profile_name] = service_manager
            service_manager.start()
        self.update_dashboard_display()

    def stop_selected_profile(self):
        profile_name = self.active_profile_name.get()
        if not profile_name: return

        if profile_name in self.running_services and self.running_services[profile_name].is_running():
            self.running_services[profile_name].stop()
            del self.running_services[profile_name]
        self.update_dashboard_display()

    def update_dashboard_loop(self):
        if self.winfo_viewable():
            self.update_dashboard_display()
        self.after(5000, self.update_dashboard_loop)

    def update_dashboard_display(self):
        service_running = self.check_service_is_running()
        
        if service_running:
            self.main_service_status_var.set("ATIVO")
            self.main_service_status_label.config(foreground="green")
        else:
            self.main_service_status_var.set("INATIVO (Serviço de automação não detectado)")
            self.main_service_status_label.config(foreground="red")

        profile_name = self.active_profile_name.get()
        if not profile_name or profile_name not in self.profiles:
            self.profile_status_var.set("Nenhum Perfil Selecionado")
            self.profile_status_label.config(foreground="orange")
            self.queue_count_var.set(0); self.sent_count_var.set(0)
            self.failed_count_var.set(0); self.duplicate_count_var.set(0)
            for i in self.queue_tree.get_children(): self.queue_tree.delete(i)
            return

        profile_is_enabled = self.profiles[profile_name].get('enabled', False)

        if service_running and profile_is_enabled:
            self.profile_status_var.set("ATIVO (EM EXECUÇÃO PELO SERVIÇO)")
            self.profile_status_label.config(foreground="green")
        elif not profile_is_enabled:
            self.profile_status_var.set("INATIVO (Desativado nas configurações do perfil)")
            self.profile_status_label.config(foreground="gray")
        else:
            self.profile_status_var.set("PENDENTE (O serviço principal está parado)")
            self.profile_status_label.config(foreground="orange")

        stats = data_manager.get_queue_stats(self.profiles[profile_name]['db_path'])
        self.queue_count_var.set(stats.get('pending', 0)); self.sent_count_var.set(stats.get('sent', 0))
        self.failed_count_var.set(stats.get('failed', 0)); self.duplicate_count_var.set(stats.get('duplicate', 0))

        if not self.queue_tree.selection():
            for i in self.queue_tree.get_children(): self.queue_tree.delete(i)
            items = data_manager.get_all_queue_items(self.profiles[profile_name]['db_path'])
            for item in items:
                filename = os.path.basename(item[1]) if item[1] else "N/A"
                file_hash = (item[6][:10] + '...') if item[6] else "N/A"
                display_item = (item[0], item[2], item[3], filename, file_hash, item[4], item[5] or "N/A")
                self.queue_tree.insert("", "end", values=display_item)
            
    def setup_dashboard(self):
        main_status_frame = ttk.Frame(self.dashboard_frame, padding=(0, 0, 0, 10))
        main_status_frame.pack(fill='x')
        self.main_service_status_var = tk.StringVar()
        self.main_service_status_label = ttk.Label(main_status_frame, textvariable=self.main_service_status_var, font=("Segoe UI", 10, "bold"), anchor='center')
        self.main_service_status_label.pack(fill='x')
        
        top_frame = ttk.Frame(self.dashboard_frame)
        top_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(top_frame, text="Monitorizar Perfil:").pack(side='left', padx=(0, 5))
        self.profile_selector = ttk.Combobox(top_frame, textvariable=self.active_profile_name, state='readonly', width=40)
        self.profile_selector.pack(side='left', fill='x', expand=True)
        self.profile_selector.bind("<<ComboboxSelected>>", self.on_profile_select)

        status_panel = ttk.LabelFrame(self.dashboard_frame, text="Status do Perfil Selecionado", padding="10")
        status_panel.pack(fill="x", expand=False)
        status_panel.columnconfigure(1, weight=1)

        status_font = ("Segoe UI", 10); status_value_font = ("Segoe UI", 10, "bold")
        self.profile_status_var = tk.StringVar()
        self.queue_count_var = tk.IntVar(); self.sent_count_var = tk.IntVar()
        self.failed_count_var = tk.IntVar(); self.duplicate_count_var = tk.IntVar()

        ttk.Label(status_panel, text="Status do Perfil:", font=status_font).grid(row=0, column=0, sticky="w")
        self.profile_status_label = ttk.Label(status_panel, textvariable=self.profile_status_var, font=status_value_font)
        self.profile_status_label.grid(row=0, column=1, sticky="w", padx=5, columnspan=3)
        
        ttk.Label(status_panel, text="Arquivos na Fila:", font=status_font).grid(row=1, column=0, sticky="w")
        ttk.Label(status_panel, textvariable=self.queue_count_var, font=status_value_font).grid(row=1, column=1, sticky="w", padx=5)
        ttk.Label(status_panel, text="Enviados (Total):", font=status_font).grid(row=2, column=0, sticky="w")
        ttk.Label(status_panel, textvariable=self.sent_count_var, font=status_value_font).grid(row=2, column=1, sticky="w", padx=5)
        ttk.Label(status_panel, text="Falhas (Total):", font=status_font).grid(row=1, column=2, sticky="w", padx=20)
        ttk.Label(status_panel, textvariable=self.failed_count_var, font=status_value_font).grid(row=1, column=3, sticky="w", padx=5)
        ttk.Label(status_panel, text="Duplicados (Total):", font=status_font).grid(row=2, column=2, sticky="w", padx=20)
        ttk.Label(status_panel, textvariable=self.duplicate_count_var, font=status_value_font).grid(row=2, column=3, sticky="w", padx=5)
        
        queue_panel = ttk.LabelFrame(self.dashboard_frame, text="Monitor da Fila", padding="10")
        queue_panel.pack(fill="both", expand=True, pady=10)
        tree_frame = ttk.Frame(queue_panel)
        tree_frame.pack(fill='both', expand=True)

        cols = ("ID", "Status", "Tentativas", "Nome do Arquivo", "Hash", "Adicionado", "Processado")
        self.queue_tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        for col in cols:
            self.queue_tree.heading(col, text=col); self.queue_tree.column(col, width=100, anchor='w')
        self.queue_tree.column("Nome do Arquivo", width=250); self.queue_tree.column("Hash", width=120)
        self.queue_tree.column("Adicionado", width=140); self.queue_tree.column("Processado", width=140)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.queue_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.queue_tree.xview)
        self.queue_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.queue_tree.grid(row=0, column=0, sticky='nsew'); vsb.grid(row=0, column=1, sticky='ns'); hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1); tree_frame.grid_columnconfigure(0, weight=1)

        button_frame = ttk.Frame(queue_panel)
        button_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(button_frame, text="Atualizar Fila", command=self.update_dashboard_display).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Tentar Novamente os Selecionados", command=self.retry_selected_items).pack(side="left", padx=5)

    def setup_logs(self):
        self.log_text_area = scrolledtext.ScrolledText(self.logs_frame, wrap=tk.WORD, state='disabled', font=("Consolas", 9))
        self.log_text_area.pack(expand=True, fill="both", pady=5)
        clear_button = ttk.Button(self.logs_frame, text="Limpar Visualização de Logs", command=self._clear_log_display)
        clear_button.pack(fill='x')

    def _clear_log_display(self):
        if messagebox.askyesno("Limpar Logs", "Tem a certeza que deseja limpar a visualização de logs? Isto não afeta o ficheiro de log salvo."):
            self.log_text_area.configure(state='normal'); self.log_text_area.delete('1.0', tk.END); self.log_text_area.configure(state='disabled')
            logging.info("Visualização de log limpa pelo utilizador.")

    def setup_settings(self):
        settings_container = ttk.Frame(self.settings_frame); settings_container.pack(expand=True, fill='both', pady=20)
        left_frame = ttk.Frame(settings_container); left_frame.pack(side='left', fill='both', expand=True, padx=(0,10))
        right_frame = ttk.Frame(settings_container); right_frame.pack(side='left', fill='y')
        ttk.Label(left_frame, text="Perfis existentes:").pack(anchor='w')
        self.profile_listbox = tk.Listbox(left_frame, height=15); self.profile_listbox.pack(fill='both', expand=True)
        self.update_profile_listbox()
        ttk.Button(right_frame, text="Criar Novo Perfil", command=self.create_profile).pack(fill='x', pady=5)
        ttk.Button(right_frame, text="Editar Perfil", command=self.edit_profile).pack(fill='x', pady=5)
        ttk.Button(right_frame, text="Apagar Perfil", command=self.delete_profile).pack(fill='x', pady=5)
        ttk.Separator(right_frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Button(right_frame, text="Importar Perfil", command=self.import_profile).pack(fill='x', pady=5)
        ttk.Button(right_frame, text="Exportar Perfil", command=self.export_profile).pack(fill='x', pady=5)
        about_frame = ttk.LabelFrame(right_frame, text="Sobre", padding=10); about_frame.pack(fill='x', pady=(20,5), side='bottom')
        ttk.Label(about_frame, text="Automatizador de Tarefas\nDesenvolvido por Lucas Melo\ne Matheus dos Santos", justify=tk.CENTER).pack()
    
    def update_profile_listbox(self):
        self.profile_listbox.delete(0, tk.END)
        for name in sorted(self.profiles.keys()):
            is_enabled = self.profiles[name].get('enabled', False)
            display_name = f"{name} {'[ATIVO]' if is_enabled else ''}"
            self.profile_listbox.insert(tk.END, display_name)

    def _get_selected_profile_name(self):
        selected_indices = self.profile_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Aviso", "Por favor, selecione um perfil.", parent=self)
            return None
        selected_text = self.profile_listbox.get(selected_indices[0])
        return selected_text.replace(' [ATIVO]', '')

    def create_profile(self):
        editor = ProfileEditor(self, existing_names=list(self.profiles.keys()))
        self.wait_window(editor)
        if editor.result:
            profile_name = editor.result['name']
            self.profiles[profile_name] = editor.result
            config_manager.save_profiles(self.profiles)
            self.update_profile_listbox(); self.update_profile_dropdown()
            messagebox.showinfo("Sucesso", f"Perfil '{profile_name}' criado com sucesso.")

    def edit_profile(self):
        old_name = self._get_selected_profile_name()
        if not old_name: return
        profile_data = self.profiles[old_name]
        existing_names = [name for name in self.profiles if name != old_name]
        editor = ProfileEditor(self, profile=profile_data, existing_names=existing_names)
        self.wait_window(editor)
        if editor.result:
            new_data = editor.result
            if old_name != new_data['name']: del self.profiles[old_name]
            self.profiles[new_data['name']] = new_data
            config_manager.save_profiles(self.profiles)
            self.update_profile_listbox(); self.update_profile_dropdown()
            messagebox.showinfo("Sucesso", f"Perfil '{new_data['name']}' atualizado com sucesso.")

    def delete_profile(self):
        profile_name = self._get_selected_profile_name()
        if not profile_name: return
        if messagebox.askyesno("Confirmar", f"Tem a certeza que deseja apagar o perfil '{profile_name}'? Os ficheiros de log e banco de dados associados não serão apagados.", parent=self):
            if profile_name in self.running_services:
                self.running_services[profile_name].stop(); del self.running_services[profile_name]
            del self.profiles[profile_name]
            config_manager.save_profiles(self.profiles)
            self.update_profile_listbox(); self.update_profile_dropdown()
            messagebox.showinfo("Sucesso", f"Perfil '{profile_name}' apagado.")
    
    def import_profile(self):
        filepath = filedialog.askopenfilename(title="Importar Perfil", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f: profile_data = json.load(f)
            if 'name' not in profile_data or 'source_path' not in profile_data: raise ValueError("Ficheiro JSON inválido.")
            profile_name = profile_data['name']
            while profile_name in self.profiles: profile_name = f"{profile_name}_importado"
            self.profiles[profile_name] = profile_data
            config_manager.save_profiles(self.profiles)
            self.update_profile_listbox(); self.update_profile_dropdown()
            messagebox.showinfo("Sucesso", f"Perfil '{profile_name}' importado com sucesso.")
        except Exception as e:
            messagebox.showerror("Erro de Importação", f"Não foi possível importar o perfil:\n{e}")

    def export_profile(self):
        profile_name = self._get_selected_profile_name()
        if not profile_name: return
        profile_data = self.profiles[profile_name]
        filepath = filedialog.asksaveasfilename(title="Exportar Perfil", defaultextension=".json", initialfile=f"{profile_name}.json", filetypes=[("JSON files", "*.json")])
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(profile_data, f, indent=4)
            messagebox.showinfo("Sucesso", f"Perfil '{profile_name}' exportado com sucesso para:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Erro de Exportação", f"Não foi possível exportar o perfil:\n{e}")

    def retry_selected_items(self):
        profile_name = self.active_profile_name.get()
        if not profile_name: return
        selected_items = self.queue_tree.selection()
        if not selected_items: messagebox.showinfo("Informação", "Nenhum item selecionado."); return
        item_ids_to_retry = [self.queue_tree.item(i, 'values')[0] for i in selected_items if self.queue_tree.item(i, 'values')[1] == 'failed']
        if not item_ids_to_retry: messagebox.showinfo("Informação", "Nenhum item com 'falha' foi selecionado para nova tentativa."); return
        db_path = self.profiles[profile_name]['db_path']
        data_manager.reset_failed_items(db_path, item_ids_to_retry)
        messagebox.showinfo("Sucesso", f"{len(item_ids_to_retry)} item(ns) foram recolocados na fila para processamento.")
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
        except Exception: pass
        finally:
            self.after(100, self.process_log_queue)

if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = MainApplication()
    app.mainloop()