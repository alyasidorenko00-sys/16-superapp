"""Запуск SuperApp."""
import tkinter as tk
from tkinter import messagebox


class SuperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SuperApp v2.0")
        self.geometry("1000x700")
        self.configure(bg="#2c3e50")

        self.utils_registry = {}
        self.active_frame = None

        self._build_sidebar()
        self._build_content()
        self._register_utilities()

        available = [name for name, cls in self.utils_registry.items() if cls is not None]
        if available:
            self._navigate(available[0])

    def _build_sidebar(self):
        self.sidebar = tk.Frame(self, width=220, bg="#34495e")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text=" SuperApp",
                 font=("Arial", 22, "bold"), bg="#34495e", fg="white").pack(pady=20)

        self.nav_btns = {}
        buttons = [
            ("schedule", " Расписание")
        ]

        for key, txt in buttons:
            btn = tk.Button(self.sidebar, text=txt, command=lambda k=key: self._navigate(k),
                            bg="#34495e", fg="white", relief="flat",
                            font=("Arial", 12), padx=20, pady=10, anchor="w")
            btn.pack(fill="x", padx=5, pady=2)
            self.nav_btns[key] = btn

    def _build_content(self):
        self.content = tk.Frame(self, bg="white")
        self.content.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def _register_utilities(self):
        try:
            from schedule_manager import ScheduleManager
            self.utils_registry["schedule"] = ScheduleManager
            print("✅ ScheduleManager загружен")
        except Exception as e:
            print(f"❌ ScheduleManager: {e}")

    def _navigate(self, key):
        if self.active_frame:
            self.active_frame.destroy()

        for btn in self.nav_btns.values():
            btn.configure(bg="#34495e")
        if key in self.nav_btns:
            self.nav_btns[key].configure(bg="#2c3e50")

        util_class = self.utils_registry.get(key)
        if util_class:
            self.active_frame = util_class(self.content)
            self.active_frame.grid(row=0, column=0, sticky="nsew")
        else:
            tk.Label(self.content, text="🛠️ В разработке",
                     font=("Arial", 24), bg="white").pack(expand=True)


if __name__ == "__main__":
    app = SuperApp()
    app.mainloop()