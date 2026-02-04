import tkinter as tk
from tkinter import ttk, messagebox
import config_manager

class ConfigApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Configurador de Autenticação - EDI Robot")
        self.geometry("400x500")
        
        self.settings = config_manager.load_settings()
        self.setup_ui()

    def setup_ui(self):
        # --- ESCOLHA DO MÉTODO ---
        lbl_frame = ttk.LabelFrame(self, text="Método de Login Principal", padding=10)
        lbl_frame.pack(fill="x", padx=10, pady=10)
        
        self.auth_var = tk.StringVar(value=self.settings.get("auth_method", "N4"))
        
        ttk.Radiobutton(lbl_frame, text="N4 (SOAP API)", variable=self.auth_var, value="N4").pack(anchor="w")
        ttk.Radiobutton(lbl_frame, text="Banco de Dados (SQL)", variable=self.auth_var, value="DATABASE").pack(anchor="w")

        # --- CAMPOS N4 ---
        n4_frame = ttk.LabelFrame(self, text="Configuração N4", padding=10)
        n4_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(n4_frame, text="URL do Argo Service:").pack(anchor="w")
        self.ent_url = ttk.Entry(n4_frame)
        self.ent_url.insert(0, self.settings.get("n4_url", ""))
        self.ent_url.pack(fill="x", pady=(0, 5))

        # Scope Grid
        scope = self.settings.get("n4_scope", {})
        grid_frm = ttk.Frame(n4_frame)
        grid_frm.pack(fill="x")
        
        self.ent_op = self._add_field(grid_frm, "Operator:", scope.get("op"), 0, 0)
        self.ent_cpx = self._add_field(grid_frm, "Complex:", scope.get("cpx"), 0, 1)
        self.ent_fac = self._add_field(grid_frm, "Facility:", scope.get("fac"), 1, 0)
        self.ent_yard = self._add_field(grid_frm, "Yard:", scope.get("yard"), 1, 1)

        # --- CAMPOS BANCO ---
        db_frame = ttk.LabelFrame(self, text="Configuração Banco", padding=10)
        db_frame.pack(fill="x", padx=10, pady=5)
        
        db = self.settings.get("db_config", {})
        self.ent_host = self._add_field(db_frame, "Host/IP:", db.get("host"), 0, 0)
        self.ent_name = self._add_field(db_frame, "Banco:", db.get("name"), 0, 1)
        # (Adicione user/pass se quiser)

        # --- BOTAO SALVAR ---
        ttk.Button(self, text="SALVAR CONFIGURAÇÃO", command=self.save_all).pack(fill="x", padx=10, pady=20)

    def _add_field(self, parent, label, value, r, c):
        f = ttk.Frame(parent)
        f.grid(row=r, column=c, padx=5, pady=2, sticky="ew")
        ttk.Label(f, text=label).pack(anchor="w")
        e = ttk.Entry(f)
        e.insert(0, value if value else "")
        e.pack(fill="x")
        return e

    def save_all(self):
        new_data = {
            "auth_method": self.auth_var.get(),
            "n4_url": self.ent_url.get(),
            "n4_scope": {
                "op": self.ent_op.get(),
                "cpx": self.ent_cpx.get(),
                "fac": self.ent_fac.get(),
                "yard": self.ent_yard.get()
            },
            "db_config": {
                "host": self.ent_host.get(),
                "name": self.ent_name.get(),
                # Adicionar user/pass na logica real
                "user": "sa", "pass": "senha"
            }
        }
        if config_manager.save_settings(new_data):
            messagebox.showinfo("Sucesso", "Configuração salva!\nO EDI-Control-App vai usar esses dados agora.")
            self.destroy()
        else:
            messagebox.showerror("Erro", "Falha ao salvar.")

if __name__ == "__main__":
    app = ConfigApp()
    app.mainloop()