# Робочий процес у сервісному центрі

## На столі техніка

1. Увімкнути iPhone, розблокувати, підключити USB.
2. На екрані — **Trust This Computer**.
3. На ПК:

```bash
cd iphone-service-diag/desktop
source .venv/bin/activate   # або Windows: .venv\Scripts\activate
python -m service_diag devices
python -m service_diag scan --out ../reports
```

4. Відкрити HTML-звіт у браузері (батарея, модель, креші).

## Тест «кнопкою» (NFC тощо)

1. Встановити **ServiceDiag** з Xcode на тестовий/клієнтський телефон (за згодою клієнта).
2. Відкрити апку → **Повний тест + NFC**.
3. Для NFC піднести **відомий робочий NFC-тег**, потім сенсор Libre.
4. **Експорт JSON** → AirDrop / кабель.

## Інтерпретація NFC

| Результат | Висновок |
|-----------|----------|
| Звичайний тег OK, Libre ні | Сенсор / апка Libre / положення |
| Жоден тег не читається | NFC flex / антена / чохол з магнітом / поганий ремонт дисплея |
| Апка каже «NFC недоступне» | Софт / entitlements / модель без reader mode |

## Syslog під час NFC

```bash
python -m service_diag syslog --duration 60 --match nfc --save ../reports/nfc_syslog.txt
```

Паралельно на телефоні запустіть тест NFC.

## Чого очікувати не варто

- Повного списку процесів як у Android.
- Фабричного Apple AST без авторизації.
- «Секретного коду» діагностики NFC в Phone.app.
