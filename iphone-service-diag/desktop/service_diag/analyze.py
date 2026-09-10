"""Heuristic analysis of crash/panic logs for service-bench hints."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PANIC_NAME_RE = re.compile(r"panic(-full)?", re.I)

# filename / content keyword → repair hypothesis (UA)
RULES: list[tuple[str, str, str]] = [
    (
        r"panic(-full)?|Kernel Panic|panicString",
        "panic",
        "Знайдено panic / panic-full. Можливі: волога на платі, КЗ, поганий шлейф, збій SoC/PMIC. Збережіть файл panic-full для історії.",
    ),
    (
        r"audio|coreaudio|asmedia|Speaker|Earpiece|AudioCodec|AppleHDA|aop.?audio",
        "audio",
        "Згадки audio в логах. Якщо немає звуку після води: перевірити динамік/слухавку/аудіокодек/шлейф, чистку від корозії, не лише ПЗ.",
    ),
    (
        r"wifi|wlan|AppleBCM|IO80211|WiFiNanny",
        "wifi",
        "Підозра на Wi‑Fi стек/модуль. Перевірити апаратний Wi‑Fi (і часто BT на одній збірці).",
    ),
    (
        r"bluetooth|BTServer|bluetoothd|BlueTool",
        "bluetooth",
        "Підозра на Bluetooth. Тест пари з навушниками/годинником; після вологи — часто спільний WiFi/BT модуль.",
    ),
    (
        r"baseband|CommCenter|Cellular|telephony|BBCrash|Baseband",
        "gsm",
        "Підозра на baseband / GSM. Перевірити SIM, мережу, антени; після вологи — baseband зона на платі.",
    ),
    (
        r"nfc|NearField|nfcd|CoreNFC",
        "nfc",
        "Підозра на NFC. Тест звичайним NFC-тегом в апці ServiceDiag; після ремонту екрана — шлейф NFC.",
    ),
    (
        r"biometr|Pearl|FaceID|SecureEnclave|mescal|BKDevice",
        "faceid",
        "Підозра на Face ID / біометрію. Після заміни екрана потрібне оригінальне спряження; софт лише покаже наявність сенсора.",
    ),
    (
        r"multitouch|Digitizer|backboardd|SpringBoard.*touch",
        "touch",
        "Підозра на тач/дисплей. Перевірити touch grid в апці; після вологи — шлейф дисплея.",
    ),
    (
        r"gas.?gauge|battery|AppleSmartBattery|powerd|thermalmonitord",
        "battery",
        "Підозра на батарею/живлення. Порівняти цикли і % у звіті; після вологи перевірити роз’єм батареї і корозію.",
    ),
]

LIQUID_NO_SOUND = [
    "Симптом: немає звуку після вологи — дуже часто ЗАЛІЗО, не «драйвер».",
    "Перевірити: нижній динамік, слухавка, аудіо IC / підсилювач, шлейфи, корозія під екраном і біля роз’єму.",
    "Софт-тест: в апці ServiceDiag → Динамік + Слухавка + Мікрофон. Якщо тон «грає» в системі, а гучності немає — динамік/механіка.",
    "Якщо тон не чути ніде (і навушники теж ні) — частіше кодек/плата/шлях аудіо.",
    "Panic-full бажано зтягнути кнопкою на Mac — якщо є kernel panic після води, фіксуйте перед ремонтом.",
]


def analyze_crash_dir(crash_dir: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "panic_full_files": [],
        "panic_files": [],
        "matched_categories": [],
        "hypotheses": [],
        "liquid_no_sound_checklist": LIQUID_NO_SOUND,
        "notes": [
            "Це евристика для СЦ, не офіційний Apple AST.",
            "Face ID / NFC / динамік повністю перевіряються лише тестами НА телефоні + очима/вухами техніка.",
        ],
    }
    if not crash_dir or not Path(crash_dir).exists():
        result["notes"].append("Папки crash reports немає — аналіз логів пропущено.")
        return result

    root = Path(crash_dir)
    texts: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if re.search(r"panic-full", name, re.I):
            result["panic_full_files"].append(str(path))
        elif re.search(r"panic", name, re.I):
            result["panic_files"].append(str(path))
        if path.stat().st_size > 2_000_000:
            continue
        if path.suffix.lower() not in {".ips", ".panic", ".log", ".txt", ".crash", ".json", ""}:
            # still try small files without suffix
            if path.suffix and path.suffix.lower() not in {".ips", ".panic", ".log", ".txt", ".crash", ".json"}:
                continue
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        texts.append((name, raw[:200_000]))

    found: dict[str, str] = {}
    blob_names = "\n".join(n for n, _ in texts)
    blob_all = blob_names + "\n" + "\n".join(t for _, t in texts)

    for pattern, cat, hypothesis in RULES:
        if re.search(pattern, blob_all, re.I):
            found[cat] = hypothesis

    if result["panic_full_files"] and "panic" not in found:
        found["panic"] = RULES[0][2]

    result["matched_categories"] = sorted(found.keys())
    result["hypotheses"] = [found[k] for k in sorted(found.keys())]

    if result["panic_full_files"]:
        result["hypotheses"].insert(
            0,
            f"Завантажено panic-full: {len(result['panic_full_files'])} файл(ів). Відкрийте їх у текстовому редакторі — там причина kernel panic.",
        )
    elif not texts:
        result["notes"].append("Crash-файлів майже немає або вони порожні — пристрій «чистий» або логи не зтягнулись.")

    return result


def analyze_battery(battery: dict[str, Any] | None) -> list[str]:
    tips: list[str] = []
    if not battery or battery.get("error"):
        tips.append("Батарею не вдалося прочитати по USB.")
        return tips
    health = battery.get("estimated_health_percent")
    summary = battery.get("summary") or {}
    cycles = summary.get("CycleCount")
    if health is not None:
        try:
            h = float(health)
            if h < 80:
                tips.append(f"Орієнтовне здоров'я батареї ~{h}% — клієнту варто пропонувати заміну АКБ.")
            elif h < 90:
                tips.append(f"Орієнтовне здоров'я батареї ~{h}% — прийнятно, але не ідеал.")
            else:
                tips.append(f"Орієнтовне здоров'я батареї ~{h}% — добре.")
        except (TypeError, ValueError):
            pass
    if cycles is not None:
        tips.append(f"Цикли зарядки: {cycles}.")
    return tips


def build_service_advice(
    *,
    info: dict[str, Any] | None = None,
    battery: dict[str, Any] | None = None,
    crash_dir: Path | str | None = None,
) -> dict[str, Any]:
    crash_path = Path(crash_dir) if crash_dir else None
    analysis = analyze_crash_dir(crash_path)
    analysis["battery_tips"] = analyze_battery(battery)
    info = info or {}
    analysis["device_line"] = (
        f"{info.get('DeviceName') or '?'} | {info.get('ProductType') or '?'} | "
        f"iOS {info.get('ProductVersion') or '?'} | BB {info.get('BasebandVersion') or 'n/a'}"
    )
    # Always attach liquid/sound guidance for wet phones (common bench case)
    analysis["always_show_sound_wet"] = LIQUID_NO_SOUND
    return analysis
