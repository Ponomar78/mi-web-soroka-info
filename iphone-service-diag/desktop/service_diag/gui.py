"""Simple double-click friendly GUI for Mac service bench."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext

from service_diag import __version__
from service_diag import collectors as C


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"ServiceDiag — діагностика iPhone ({__version__})")
        self.geometry("720x520")
        self.minsize(640, 440)

        root_dir = Path(__file__).resolve().parents[2]
        self.reports_dir = root_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        top = tk.Frame(self, padx=12, pady=10)
        top.pack(fill=tk.X)

        tk.Label(
            top,
            text="Підключіть iPhone кабелем і натисніть Trust.\nПотім одну з кнопок нижче.",
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        btns = tk.Frame(self, padx=12)
        btns.pack(fill=tk.X)

        self._mk_btn(btns, "1. Список пристроїв", self.on_devices).pack(side=tk.LEFT, padx=(0, 8))
        self._mk_btn(btns, "2. Повний скан (звіт)", self.on_scan).pack(side=tk.LEFT, padx=(0, 8))
        self._mk_btn(btns, "3. Тільки батарея", self.on_battery).pack(side=tk.LEFT, padx=(0, 8))
        self._mk_btn(btns, "Відкрити звіти", self.on_open_reports).pack(side=tk.LEFT)

        self.status = tk.StringVar(value="Готово.")
        tk.Label(self, textvariable=self.status, anchor=tk.W, padx=12, pady=6).pack(fill=tk.X)

        self.log = scrolledtext.ScrolledText(self, wrap=tk.WORD, font=("Menlo", 12))
        self.log.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self._append(
            "ServiceDiag для Mac\n"
            "NFC апаратний тест — лише в апці на телефоні (папка ios-app).\n"
            "Ця програма читає інфо / батарею / креші по USB.\n"
        )

        self._busy = False

    def _mk_btn(self, parent: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(parent, text=text, command=command, padx=10, pady=6)

    def _append(self, text: str) -> None:
        self.log.insert(tk.END, text + ("\n" if not text.endswith("\n") else ""))
        self.log.see(tk.END)

    def _set_busy(self, busy: bool, status: str) -> None:
        self._busy = busy
        self.status.set(status)

    def _run_bg(self, title: str, fn) -> None:
        if self._busy:
            messagebox.showinfo("Зачекайте", "Зараз уже виконується інша операція.")
            return

        def worker() -> None:
            self.after(0, lambda: self._set_busy(True, f"{title}…"))
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                err = str(exc).strip() or repr(exc)

                def fail() -> None:
                    self._set_busy(False, "Помилка.")
                    self._append(f"\n❌ {title}: {err}\n")
                    messagebox.showerror(
                        "Помилка",
                        f"{err}\n\nПеревірте кабель, Trust на iPhone, і що Python/залежності встановлені.",
                    )

                self.after(0, fail)
                return

            def ok() -> None:
                self._set_busy(False, "Готово.")
                self._append(f"\n✅ {title}\n{result}\n")

            self.after(0, ok)

        threading.Thread(target=worker, daemon=True).start()

    def on_devices(self) -> None:
        def job() -> str:
            devices = C.list_devices()
            if not devices:
                return "Пристроїв не знайдено."
            lines = [f"- {d.get('serial')} ({d.get('connection_type')})" for d in devices]
            return "Знайдено:\n" + "\n".join(lines)

        self._run_bg("Список пристроїв", job)

    def on_battery(self) -> None:
        def job() -> str:
            data = C.collect_battery()
            return json.dumps(data, indent=2, ensure_ascii=False, default=str)

        self._run_bg("Батарея", job)

    def on_scan(self) -> None:
        def job() -> str:
            report = C.full_scan(self.reports_dir, pull_crash=True)
            html = report.get("report_html")
            return (
                f"HTML: {html}\n"
                f"JSON: {report.get('report_json')}\n"
                f"Батарея (оцінка): {((report.get('battery') or {}).get('estimated_health_percent'))}%"
            )

        self._run_bg("Повний скан", job)

    def on_open_reports(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(self.reports_dir),
            title="Звіти",
            filetypes=[("HTML/JSON", "*.html *.json"), ("All", "*.*")],
        )
        if path:
            self._append(f"Обрано файл: {path}")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
