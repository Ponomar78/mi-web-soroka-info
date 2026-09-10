# iPhone Service Diagnostics (СЦ)

Інструмент для сервісного центру: швидка діагностика iPhone по USB + тести на самому телефоні.

## Що реально можливо на iPhone (без джейлбрейку)

| Можна | Не можна (на стоковому iOS) |
|--------|------------------------------|
| Інфо пристрою, UDID, модель, iOS | Повний список усіх процесів як у Android |
| Батарея / цикли (через diagnostics) | Фабричний AST2 / Apple Service Toolkit |
| Crash reports, syslog | Глибокий hardware dump NFC-контролера |
| Встановити свою тест-апку | «Секретні коди» як `*#0*#` на Android |
| Тест NFC / камери / сенсорів **в апці** | Віддалений тест NFC тільки з ПК без апки |

Apple не дає стороннім програмам повний доступ до «усіх багів і процесів». Офіційна глибока діагностика — **Apple Diagnostics / AST** (авторизовані СЦ).  
Цей проєкт — практичний **швидкий чеклист** для звичайного ремонту.

## Архітектура

```
[Технік] → ПК (Python CLI по USB) → інфо, батарея, креші, звіт HTML
         → iPhone (Swift апка)     → NFC, вібро, екран, камера, динамік…
```

1. Підключили кабель, довіра («Trust»).
2. На ПК: `python -m service_diag scan` — звіт.
3. На телефоні: апка **ServiceDiag** → кнопка «Повний тест» (NFC — піднести тег/датчик Libre).

## Швидкий старт (ПК)

```bash
cd iphone-service-diag/desktop
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Список пристроїв
python -m service_diag devices

# Повний звіт у ../reports/
python -m service_diag scan --out ../reports
```

Потрібен кабель USB, увімкнений iPhone, підтвердження «Довіряти цьому комп’ютеру».  
На Linux може знадобитись `usbmuxd`. На Windows — iTunes / Apple Mobile Device Support.

### Корисні команди

```bash
python -m service_diag info
python -m service_diag battery
python -m service_diag crashes --out ../reports/crashes
python -m service_diag syslog --duration 30
python -m service_diag scan --out ../reports
```

## Апка на iPhone (тести кнопкою)

Джерело: `ios-app/ServiceDiag/`.  
Збірка: Mac + Xcode + Apple Developer (або безкоштовний Apple ID для себе на 7 днів).

Тести в апці:
- NFC (Core NFC) — читання тега / медичного сенсора
- Вібрація, екран (touch grid), яскравість
- Акселерометр / гіроскоп
- Камера (прев’ю), мікрофон (рівень)
- Динамік / наушник (тон)
- Мережа (Wi‑Fi / стільниковий статус з API)
- Експорт JSON-звіту (AirDrop / Files)

Деталі: [ios-app/README.md](ios-app/README.md).

## NFC і глюкозні сенсори

Часте «піднесення» до Libre **майже не «вбиває»** NFC-антену.  
Якщо два телефони підряд не читають — спочатку сенсор/чохол/місце прикладання.  
У апці: «Тест NFC» → якщо звичайний NFC-тег читається, а Libre ні — проблема не в антені телефону.

## Обмеження відповідальності

Інструмент для діагностики пристроїв клієнтів у вашому СЦ за їх згодою.  
Не обходить активаційний блокування / MDM / Activation Lock.
