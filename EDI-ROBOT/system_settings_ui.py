import tkinter as tk
from tkinter import ttk, messagebox
import config_manager

class SystemSettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Configurações do Sistema e Autenticação")
        self.geometry("500x450")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Centraliza
        self.geometry(f"+{parent.winfo_rootx() + 50}+{parent.winfo_rooty() + 50}")
        
        self.settings = config_manager.load_system_settings()
        self.setup_ui()
        
    def setup_ui(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill='both', expand=True)

        # --- SELEÇÃO DO MÉTODO ---
        ttk.Label(main_frame, text="Método de Autenticação Principal:", font=("Segoe UI", 10, "bold")).pack(anchor='w')
        self.auth_method_var = tk.StringVar(value=self.settings.get("auth_method", "N4"))
        
        method_frame = ttk.Frame(main_frame)
        method_frame.pack(fill='x', pady=(5, 15))
        
        rb_n4 = ttk.Radiobutton(method_frame, text="N4 (SOAP API)", variable=self.auth_method_var, value="N4")
        rb_n4.pack(side='left', padx=(0, 20))
        
        rb_db = ttk.Radiobutton(method_frame, text="Banco de Dados (SQL)", variable=self.auth_method_var, value="DATABASE")
        rb_db.pack(side='left')

        # --- ABAS DE CONFIGURAÇÃO ---
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=5)
        
        self.tab_n4 = ttk.Frame(notebook, padding=15)
        self.tab_db = ttk.Frame(notebook, padding=15)
        
        notebook.add(self.tab_n4, text="Configuração N4")
        notebook.add(self.tab_db, text="Configuração Banco")
        
        self._build_n4_tab()
        self._build_db_tab()

        # --- BOTÕES DE AÇÃO ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(20, 0))
        
        ttk.Button(btn_frame, text="Salvar Configurações", command=self.save, style="Accent.TButton").pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=self.destroy).pack(side='right')

    def _build_n4_tab(self):
        self.entry_n4_url = self._add_field(self.tab_n4, "N4 Argo URL:", self.settings.get("n4_api_url", ""))
        
        # Frame de Scope
        scope_frame = ttk.LabelFrame(self.tab_n4, text="N4 Scope (Topology)", padding=10)
        scope_frame.pack(fill='x', pady=10)
        
        self.entry_op = self._add_field(scope_frame, "Operator ID:", self.settings.get("n4_scope_operator", "APMT"))
        self.entry_cpx = self._add_field(scope_frame, "Complex ID:", self.settings.get("n4_scope_complex", "BRPEC"))
        self.entry_fac = self._add_field(scope_frame, "Facility ID:", self.settings.get("n4_scope_facility", "PEC"))
        self.entry_yard = self._add_field(scope_frame, "Yard ID:", self.settings.get("n4_scope_yard", "PEC"))

    def _build_db_tab(self):
        ttk.Label(self.tab_db, text="Credenciais para conexão com SQL Server:", font=("Segoe UI", 9, "italic")).pack(anchor='w', pady=(0, 10))
        
        self.entry_db_host = self._add_field(self.tab_db, "Servidor (Host/IP):", self.settings.get("db_host", ""))
        self.entry_db_name = self._add_field(self.tab_db, "Nome do Banco:", self.settings.get("db_name", ""))
        self.entry_db_user = self._add_field(self.tab_db, "Usuário SQL:", self.settings.get("db_user", ""))
        self.entry_db_pass = self._add_field(self.tab_db, "Senha SQL:", self.settings.get("db_pass", ""), is_password=True)

    def _add_field(self, parent, label_text, value, is_password=False):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=2)
        ttk.Label(frame, text=label_text, width=20).pack(side='left')
        entry = ttk.Entry(frame, show="*" if is_password else None)
        entry.insert(0, str(value))
        entry.pack(side='right', fill='x', expand=True)
        return entry

    def save(self):
        new_settings = self.settings.copy()
        
        # Geral
        new_settings["auth_method"] = self.auth_method_var.get()
        
        # N4
        new_settings["n4_api_url"] = self.entry_n4_url.get().strip()
        new_settings["n4_scope_operator"] = self.entry_op.get().strip()
        new_settings["n4_scope_complex"] = self.entry_cpx.get().strip()
        new_settings["n4_scope_facility"] = self.entry_fac.get().strip()
        new_settings["n4_scope_yard"] = self.entry_yard.get().strip()
        
        # DB
        new_settings["db_host"] = self.entry_db_host.get().strip()
        new_settings["db_name"] = self.entry_db_name.get().strip()
        new_settings["db_user"] = self.entry_db_user.get().strip()
        new_settings["db_pass"] = self.entry_db_pass.get().strip()
        
        if config_manager.save_system_settings(new_settings):
            messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!\nReinicie o aplicativo para aplicar as mudanças de autenticação.")
            self.destroy()
        else:
            messagebox.showerror("Erro", "Falha ao salvar configurações.")