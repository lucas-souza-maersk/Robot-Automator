import tkinter as tk
from tkinter import ttk, scrolledtext

class AppUI(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("retina gateway service - americas region")
        self.geometry("800x600")

        self.resizable(False, False)

        self.attributes('-toolwindow', True)  

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")

        self._create_dashboard_tab()
        self._create_directories_tab()
        self._create_kafka_tab()
        self._create_logs_tab()
        self._create_about_tab()

    def _create_dashboard_tab(self):
        dashboard_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(dashboard_frame, text='dashboard')

    def _create_directories_tab(self):
        dir_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(dir_frame, text='directories config')

    def _create_kafka_tab(self):
        kafka_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(kafka_frame, text='kafka config')

    def _create_logs_tab(self):
        logs_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(logs_frame, text='live logs')

        log_text_area = scrolledtext.ScrolledText(logs_frame, wrap=tk.WORD, state='disabled')
        log_text_area.pack(expand=True, fill="both")
        self.log_text_area = log_text_area

    def _create_about_tab(self):
        about_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(about_frame, text='about')

        about_label = ttk.Label(about_frame, text="retina gateway service v1.0\n\ndeveloped for apm terminals - americas region.")
        about_label.pack(pady=20)

    def update_log_display(self, message):
        self.log_text_area.configure(state='normal')
        self.log_text_area.insert(tk.END, message)
        self.log_text_area.configure(state='disabled')
        self.log_text_area.yview(tk.END)

if __name__ == "__main__":
    app = AppUI()
    app.mainloop()