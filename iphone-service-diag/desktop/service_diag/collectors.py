"""Collectors for connected iPhone diagnostics (async pymobiledevice3)."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(coro):
    return asyncio.run(coro)


async def _lockdown(udid: str | None = None):
    from pymobiledevice3.lockdown import create_using_usbmux

    if udid:
        return await create_using_usbmux(serial=udid)
    return await create_using_usbmux()


async def _list_devices_async() -> list[dict[str, Any]]:
    from pymobiledevice3.usbmux import list_devices as usbmux_list

    devices = []
    for dev in await usbmux_list():
        devices.append(
            {
                "serial": getattr(dev, "serial", None),
                "connection_type": str(getattr(dev, "connection_type", "usb")),
            }
        )
    return devices


def list_devices() -> list[dict[str, Any]]:
    return _run(_list_devices_async())


async def _collect_info_async(udid: str | None = None) -> dict[str, Any]:
    lockdown = await _lockdown(udid)
    keys = [
        "DeviceName",
        "ProductType",
        "ProductVersion",
        "BuildVersion",
        "SerialNumber",
        "UniqueDeviceID",
        "HardwareModel",
        "DeviceClass",
        "CPUArchitecture",
        "WiFiAddress",
        "BluetoothAddress",
        "ModelNumber",
        "RegionInfo",
        "TimeZone",
        "PasswordProtected",
        "BrickState",
        "ActivationState",
        "TelephonyCapability",
        "BasebandVersion",
    ]
    info: dict[str, Any] = {"collected_at": _utc_now()}
    for key in keys:
        try:
            info[key] = await lockdown.get_value(key=key)
        except Exception:
            info[key] = None
    try:
        info["all_values"] = dict(await lockdown.get_value())
    except Exception as exc:
        info["all_values_error"] = str(exc)
    return info


def collect_info(udid: str | None = None) -> dict[str, Any]:
    return _run(_collect_info_async(udid))


async def _collect_battery_async(udid: str | None = None) -> dict[str, Any]:
    from pymobiledevice3.services.diagnostics import DiagnosticsService

    lockdown = await _lockdown(udid)
    diag = DiagnosticsService(lockdown)
    try:
        raw = await diag.get_battery()
    except Exception as exc:
        return {"error": str(exc), "collected_at": _utc_now()}

    interesting = [
        "CycleCount",
        "DesignCapacity",
        "AppleRawCurrentCapacity",
        "AppleRawMaxCapacity",
        "NominalChargeCapacity",
        "CurrentCapacity",
        "MaxCapacity",
        "Temperature",
        "Voltage",
        "IsCharging",
        "ExternalConnected",
        "FullyCharged",
        "BatteryInstalled",
        "Serial",
        "ManufacturerData",
    ]
    summary = {k: raw.get(k) for k in interesting if isinstance(raw, dict) and k in raw}
    health = None
    if isinstance(raw, dict):
        design = raw.get("DesignCapacity")
        current_max = (
            raw.get("NominalChargeCapacity")
            or raw.get("AppleRawMaxCapacity")
            or raw.get("MaxCapacity")
        )
        try:
            if design and current_max and float(design) > 0:
                health = round(100.0 * float(current_max) / float(design), 1)
        except (TypeError, ValueError):
            health = None

    return {
        "collected_at": _utc_now(),
        "estimated_health_percent": health,
        "summary": summary,
        "raw": raw if isinstance(raw, dict) else {"value": raw},
    }


def collect_battery(udid: str | None = None) -> dict[str, Any]:
    return _run(_collect_battery_async(udid))


async def _collect_apps_async(udid: str | None = None) -> list[dict[str, Any]]:
    from pymobiledevice3.services.installation_proxy import InstallationProxyService

    lockdown = await _lockdown(udid)
    apps: list[dict[str, Any]] = []
    try:
        async with InstallationProxyService(lockdown=lockdown) as iproxy:
            mapping = await iproxy.get_apps()
            for bundle_id, meta in mapping.items():
                apps.append(
                    {
                        "bundle_id": bundle_id,
                        "name": meta.get("CFBundleDisplayName") or meta.get("CFBundleName"),
                        "version": meta.get("CFBundleShortVersionString")
                        or meta.get("CFBundleVersion"),
                    }
                )
    except Exception as exc:
        return [{"error": str(exc)}]
    apps.sort(key=lambda a: (a.get("name") or a.get("bundle_id") or "").lower())
    return apps


def collect_apps(udid: str | None = None) -> list[dict[str, Any]]:
    return _run(_collect_apps_async(udid))


async def _pull_crashes_async(
    out_dir: Path, udid: str | None = None, erase: bool = False
) -> dict[str, Any]:
    from pymobiledevice3.services.crash_reports import CrashReportsManager

    out_dir.mkdir(parents=True, exist_ok=True)
    lockdown = await _lockdown(udid)
    try:
        async with CrashReportsManager(lockdown) as manager:
            await manager.pull(str(out_dir), erase=erase)
        files = sorted(p.name for p in out_dir.rglob("*") if p.is_file())
        return {
            "collected_at": _utc_now(),
            "path": str(out_dir.resolve()),
            "file_count": len(files),
            "files_sample": files[:50],
        }
    except Exception as exc:
        return {"error": str(exc), "path": str(out_dir.resolve())}


def pull_crashes(out_dir: Path, udid: str | None = None, erase: bool = False) -> dict[str, Any]:
    return _run(_pull_crashes_async(out_dir, udid=udid, erase=erase))


async def _stream_syslog_async(
    duration: int = 20, udid: str | None = None, match: str | None = None
) -> list[str]:
    from pymobiledevice3.services.os_trace import OsTraceService

    lockdown = await _lockdown(udid)
    lines: list[str] = []
    end = time.time() + duration
    try:
        async with OsTraceService(lockdown=lockdown) as trace:
            async for entry in trace.syslog():
                text = str(entry)
                if match and match.lower() not in text.lower():
                    if time.time() >= end:
                        break
                    continue
                lines.append(text)
                if time.time() >= end or len(lines) >= 5000:
                    break
    except TypeError:
        # Older/newer API without async context manager
        try:
            service = OsTraceService(lockdown=lockdown)
            async for entry in service.syslog():
                text = str(entry)
                if match and match.lower() not in text.lower():
                    if time.time() >= end:
                        break
                    continue
                lines.append(text)
                if time.time() >= end or len(lines) >= 5000:
                    break
        except Exception as exc:
            lines.append(f"ERROR: {exc}")
    except Exception as exc:
        lines.append(f"ERROR: {exc}")
    return lines


def stream_syslog(duration: int = 20, udid: str | None = None, match: str | None = None) -> list[str]:
    return _run(_stream_syslog_async(duration=duration, udid=udid, match=match))


def try_nfc_related_hints(info: dict[str, Any]) -> list[str]:
    hints = [
        "NFC antenna / controller self-test is NOT available over USB on stock iOS.",
        "Use the on-device ServiceDiag app → NFC test with a known-good NFC tag.",
        "If a generic NFC tag works but Libre/glucose sensor does not → sensor/app issue, not phone antenna.",
        "If NO NFC tag works → suspect NFC flex/antenna, case/magnet, or after-market screen repair.",
    ]
    product = (info.get("ProductType") or "") if isinstance(info, dict) else ""
    if product:
        hints.insert(
            0,
            f"Model: {product}. NFC reader for tags requires iPhone 7+; Background Tag Reading XS+.",
        )
    return hints


async def _full_scan_async(
    out_dir: Path, udid: str | None = None, pull_crash: bool = True
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report: dict[str, Any] = {
        "tool": "iphone-service-diag",
        "version": "0.1.0",
        "collected_at": _utc_now(),
        "udid_arg": udid,
    }

    console.print("[bold]1/4 Device info…[/bold]")
    report["info"] = await _collect_info_async(udid)

    console.print("[bold]2/4 Battery…[/bold]")
    report["battery"] = await _collect_battery_async(udid)

    console.print("[bold]3/4 Apps…[/bold]")
    report["apps"] = await _collect_apps_async(udid)

    if pull_crash:
        console.print("[bold]4/4 Crash reports…[/bold]")
        crash_dir = out_dir / f"crashes_{stamp}"
        report["crashes"] = await _pull_crashes_async(crash_dir, udid=udid)
    else:
        report["crashes"] = {"skipped": True}

    report["nfc_hints"] = try_nfc_related_hints(report.get("info") or {})

    json_path = out_dir / f"scan_{stamp}.json"
    html_path = out_dir / f"scan_{stamp}.html"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    html_path.write_text(render_html(report), encoding="utf-8")
    report["report_json"] = str(json_path.resolve())
    report["report_html"] = str(html_path.resolve())
    return report


def full_scan(out_dir: Path, udid: str | None = None, pull_crash: bool = True) -> dict[str, Any]:
    return _run(_full_scan_async(out_dir, udid=udid, pull_crash=pull_crash))


def render_html(report: dict[str, Any]) -> str:
    info = report.get("info") or {}
    battery = report.get("battery") or {}
    crashes = report.get("crashes") or {}
    apps = report.get("apps") or []
    hints = report.get("nfc_hints") or []

    def esc(v: Any) -> str:
        return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    rows_info = "".join(
        f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>"
        for k, v in info.items()
        if k not in ("all_values", "all_values_error")
    )
    bat_sum = battery.get("summary") or {}
    rows_bat = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in bat_sum.items())
    hints_li = "".join(f"<li>{esc(h)}</li>" for h in hints)
    apps_preview = "".join(
        f"<li>{esc(a.get('name'))} — {esc(a.get('bundle_id'))} ({esc(a.get('version'))})</li>"
        for a in apps[:40]
        if "error" not in a
    )

    return f"""<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="utf-8"/>
  <title>iPhone Service Scan</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f6f7f9; color: #111; }}
    h1,h2 {{ margin-bottom: .4rem; }}
    .card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.2rem; margin: 1rem 0; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th,td {{ text-align: left; padding: .35rem .5rem; border-bottom: 1px solid #eee; vertical-align: top; }}
    th {{ width: 28%; color: #444; }}
    .warn {{ color: #b60; }}
  </style>
</head>
<body>
  <h1>iPhone Service Diagnostics</h1>
  <p>Зібрано: <strong>{esc(report.get("collected_at"))}</strong></p>

  <div class="card">
    <h2>Пристрій</h2>
    <table>{rows_info}</table>
  </div>

  <div class="card">
    <h2>Батарея</h2>
    <p>Орієнтовне здоров'я: <strong>{esc(battery.get("estimated_health_percent"))}%</strong>
       <span class="warn">(оцінка з IORegistry, не офіційний Apple Battery Health)</span></p>
    <table>{rows_bat}</table>
  </div>

  <div class="card">
    <h2>Crash reports</h2>
    <p>Файлів: {esc(crashes.get("file_count", crashes.get("skipped", crashes.get("error"))))}</p>
    <p>Шлях: <code>{esc(crashes.get("path"))}</code></p>
  </div>

  <div class="card">
    <h2>NFC / швидкі підказки</h2>
    <ul>{hints_li}</ul>
  </div>

  <div class="card">
    <h2>Додатки (перші 40)</h2>
    <ul>{apps_preview or "<li>немає даних</li>"}</ul>
    <p>Всього: {len(apps)}</p>
  </div>
</body>
</html>
"""
