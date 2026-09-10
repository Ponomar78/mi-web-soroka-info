"""Simple double-click friendly GUI for Mac service bench."""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "Немає tkinter. На Mac встановіть Python з https://www.python.org/downloads/\n"
        "або: brew install python-tk"
    ) from exc

from service_diag import __version__
from service_diag import collectors as C
from service_diag.analyze import build_service_advice


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"ServiceDiag — діагностика iPhone ({__version__})")
        self.geometry("820x640")
        self.minsize(700, 520)

        root_dir = Path(__file__).resolve().parents[2]
        self.reports_dir = root_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.last_crash_dir: Path | None = None

        top = tk.Frame(self, padx=12, pady=10)
        top.pack(fill=tk.X)

        tk.Label(
            top,
            text=(
                "USB: інфо, батарея, Wi‑Fi, crash/panic-full, підказки ремонту.\n"
                "Face ID / NFC / звук «на слух» — апка на iPhone (папка ios-app) або ручний тест."
            ),
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        row1 = tk.Frame(self, padx=12)
        row1.pack(fill=tk.X, pady=(0, 6))
        self._mk_btn(row1, "Пристрої", self.on_devices).pack(side=tk.LEFT, padx=(0, 6))
        self._mk_btn(row1, "ПОВНИЙ СКАН + звіт", self.on_scan).pack(side=tk.LEFT, padx=(0, 6))
        self._mk_btn(row1, "Батарея", self.on_battery).pack(side=tk.LEFT, padx=(0, 6))
        self._mk_btn(row1, "Wi‑Fi лог", self.on_wifi).pack(side=tk.LEFT, padx=(0, 6))

        row2 = tk.Frame(self, padx=12)
        row2.pack(fill=tk.X, pady=(0, 6))
        self._mk_btn(row2, "Panic-full / креші", self.on_crashes).pack(side=tk.LEFT, padx=(0, 6))
        self._mk_btn(row2, "Аналіз (звук/вода)", self.on_analyze).pack(side=tk.LEFT, padx=(0, 6))
        self._mk_btn(row2, "Syslog audio 30с", self.on_syslog_audio).pack(side=tk.LEFT, padx=(0, 6))
        self._mk_btn(row2, "Відкрити папку звітів", self.on_open_folder).pack(side=tk.LEFT, padx=(0, 6))

        self.status = tk.StringVar(value="Готово.")
        tk.Label(self, textvariable=self.status, anchor=tk.W, padx=12, pady=6).pack(fill=tk.X)

        self.log = scrolledtext.ScrolledText(self, wrap=tk.WORD, font=("Menlo", 12))
        self.log.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self._append(
            "ServiceDiag для СЦ\n"
            "1) Підключіть iPhone → Trust\n"
            "2) Натисніть «ПОВНИЙ СКАН + звіт»\n"
            "3) Відкрийте HTML — там panic-full і можливі проблеми\n"
            "Немає звуку після води → дивіться блок у звіті + тест динаміка на телефоні.\n"
        )

        self._busy = False

    def _mk_btn(self, parent: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(parent, text=text, command=command, padx=8, pady=5)

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
                        f"{err}\n\nКабель, Trust, розблокований iPhone.",
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
            advice = build_service_advice(battery=data)
            return (
                json.dumps(data, indent=2, ensure_ascii=False, default=str)
                + "\n\nПідказки:\n- "
                + "\n- ".join(advice.get("battery_tips") or [])
            )

        self._run_bg("Батарея", job)

    def on_wifi(self) -> None:
        def job() -> str:
            data = C.collect_wifi()
            return json.dumps(data, indent=2, ensure_ascii=False, default=str)

        self._run_bg("Wi‑Fi", job)

    def on_crashes(self) -> None:
        def job() -> str:
            from datetime import datetime

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            crash_dir = self.reports_dir / f"crashes_{stamp}"
            result = C.pull_crashes(crash_dir)
            self.last_crash_dir = crash_dir if not result.get("error") else None
            advice = build_service_advice(crash_dir=self.last_crash_dir)
            panic = advice.get("panic_full_files") or []
            return (
                json.dumps(result, indent=2, ensure_ascii=False, default=str)
                + f"\n\npanic-full знайдено: {len(panic)}\n"
                + "\n".join(panic[:15])
            )

        self._run_bg("Crash / panic-full", job)

    def on_analyze(self) -> None:
        def job() -> str:
            crash = self.last_crash_dir
            if crash is None:
                # try newest crashes_* folder
                dirs = sorted(self.reports_dir.glob("crashes_*"), key=lambda p: p.stat().st_mtime, reverse=True)
                crash = dirs[0] if dirs else None
            bat = None
            try:
                bat = C.collect_battery()
            except Exception:  # noqa: BLE001
                bat = None
            info = None
            try:
                info = C.collect_info()
            except Exception:  # noqa: BLE001
                info = None
            advice = build_service_advice(info=info, battery=bat, crash_dir=crash)
            lines = [
                advice.get("device_line") or "",
                "",
                "=== Ймовірні проблеми ===",
                *[f"• {h}" for h in (advice.get("hypotheses") or ["Немає збігів у логах"])],
                "",
                "=== Батарея ===",
                *[f"• {h}" for h in (advice.get("battery_tips") or [])],
                "",
                "=== Немає звуку / мокрий ===",
                *[f"• {h}" for h in (advice.get("always_show_sound_wet") or [])],
                "",
                f"panic-full файлів: {len(advice.get('panic_full_files') or [])}",
            ]
            return "\n".join(lines)

        self._run_bg("Аналіз", job)

    def on_syslog_audio(self) -> None:
        def job() -> str:
            lines = C.stream_syslog(duration=30, match="audio")
            path = self.reports_dir / "syslog_audio.txt"
            path.write_text("\n".join(lines), encoding="utf-8")
            return f"Збережено {path}\nРядків: {len(lines)}\n(Під час запису увімкніть музику / дзвінок на iPhone)"

        self._run_bg("Syslog audio", job)

    def on_scan(self) -> None:
        def job() -> str:
            report = C.full_scan(self.reports_dir, pull_crash=True)
            crash_path = (report.get("crashes") or {}).get("path")
            if crash_path:
                self.last_crash_dir = Path(crash_path)
            advice = report.get("advice") or {}
            html = report.get("report_html")
            # try open HTML on Mac
            if html:
                try:
                    subprocess.Popen(["open", html])  # noqa: S603,S607
                except OSError:
                    pass
            return (
                f"HTML: {html}\n"
                f"JSON: {report.get('report_json')}\n"
                f"Батарея: {((report.get('battery') or {}).get('estimated_health_percent'))}%\n"
                f"Категорії: {', '.join(advice.get('matched_categories') or []) or 'немає'}\n"
                f"panic-full: {len(advice.get('panic_full_files') or [])}\n\n"
                + "\n".join(f"• {h}" for h in (advice.get("hypotheses") or [])[:8])
            )

        self._run_bg("Повний скан", job)

    def on_open_folder(self) -> None:
        try:
            subprocess.Popen(["open", str(self.reports_dir)])  # noqa: S603,S607
        except OSError:
            filedialog.askopenfilename(initialdir=str(self.reports_dir))


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
