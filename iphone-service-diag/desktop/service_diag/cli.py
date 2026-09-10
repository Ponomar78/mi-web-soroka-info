"""CLI for service-center iPhone diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from service_diag import __version__
from service_diag import collectors as C

app = typer.Typer(
    add_completion=False,
    help="Діагностика iPhone для сервісного центру (USB).",
    no_args_is_help=True,
)
console = Console()


def _udid_opt() -> Optional[str]:
    return None


@app.command("devices")
def devices_cmd() -> None:
    """Список підключених iPhone/iPad."""
    try:
        devices = C.list_devices()
    except Exception as exc:
        msg = str(exc).strip() or repr(exc)
        console.print(f"[red]Помилка:[/red] {msg}")
        console.print(
            "[dim]Перевірте: кабель, usbmuxd (Linux), iTunes/Apple Mobile Device (Windows), Trust на телефоні.[/dim]"
        )
        raise typer.Exit(1) from exc

    if not devices:
        console.print("[yellow]Пристроїв не знайдено. Перевірте кабель і Trust.[/yellow]")
        raise typer.Exit(2)

    table = Table(title="Підключені пристрої")
    table.add_column("UDID / Serial")
    table.add_column("Connection")
    for d in devices:
        table.add_row(str(d.get("serial")), str(d.get("connection_type")))
    console.print(table)


@app.command("info")
def info_cmd(udid: Optional[str] = typer.Option(None, help="UDID пристрою")) -> None:
    """Базова інформація про телефон."""
    data = C.collect_info(udid)
    for k, v in data.items():
        if k in ("all_values",):
            continue
        console.print(f"[bold]{k}[/bold]: {v}")


@app.command("battery")
def battery_cmd(udid: Optional[str] = typer.Option(None, help="UDID пристрою")) -> None:
    """Батарея / цикли (IORegistry)."""
    data = C.collect_battery(udid)
    console.print_json(json.dumps(data, default=str, ensure_ascii=False))


@app.command("crashes")
def crashes_cmd(
    out: Path = typer.Option(Path("crashes_out"), help="Папка для crash reports"),
    udid: Optional[str] = typer.Option(None, help="UDID пристрою"),
    erase: bool = typer.Option(False, help="Видалити з телефону після копіювання"),
) -> None:
    """Зтягнути crash reports з телефону."""
    result = C.pull_crashes(out, udid=udid, erase=erase)
    console.print_json(json.dumps(result, default=str, ensure_ascii=False))


@app.command("syslog")
def syslog_cmd(
    duration: int = typer.Option(20, help="Секунд запису syslog"),
    match: Optional[str] = typer.Option(None, help="Фільтр підрядка (напр. nfc)"),
    udid: Optional[str] = typer.Option(None, help="UDID пристрою"),
    save: Optional[Path] = typer.Option(None, help="Зберегти у файл"),
) -> None:
    """Живий syslog (корисно під час тесту NFC в апці)."""
    console.print(f"[cyan]Слухаю syslog {duration}s…[/cyan] Піднесіть тег / запустіть тест на телефоні.")
    lines = C.stream_syslog(duration=duration, udid=udid, match=match)
    text = "\n".join(lines)
    if save:
        save.write_text(text, encoding="utf-8")
        console.print(f"[green]Збережено:[/green] {save}")
    else:
        console.print(text[-20000:] if len(text) > 20000 else text)


@app.command("scan")
def scan_cmd(
    out: Path = typer.Option(Path("reports"), help="Папка звітів"),
    udid: Optional[str] = typer.Option(None, help="UDID пристрою"),
    no_crashes: bool = typer.Option(False, help="Не тягнути crash reports"),
) -> None:
    """Повний швидкий скан → JSON + HTML звіт."""
    report = C.full_scan(out, udid=udid, pull_crash=not no_crashes)
    console.print(f"[green]JSON:[/green] {report.get('report_json')}")
    console.print(f"[green]HTML:[/green] {report.get('report_html')}")
    health = (report.get("battery") or {}).get("estimated_health_percent")
    if health is not None:
        console.print(f"Батарея (оцінка): [bold]{health}%[/bold]")
    console.print("[bold]NFC:[/bold] апаратний тест тільки в апці ServiceDiag на телефоні.")


@app.command("version")
def version_cmd() -> None:
    console.print(__version__)


if __name__ == "__main__":
    app()
