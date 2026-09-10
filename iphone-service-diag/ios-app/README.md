# ServiceDiag — тести на самому iPhone

SwiftUI-апка для сервісного центру: натиснув кнопку → прогнав тести → JSON-звіт.

## Збірка (потрібен Mac + Xcode)

1. Відкрийте Xcode → **File → New → Project → App** (iOS, SwiftUI, Bundle ID напр. `ua.servicecenter.ServiceDiag`).
2. Скопіюйте файли з цієї папки в проєкт (або створіть проєкт і замініть `ContentView` / додайте файли).
3. У **Signing & Capabilities** додайте:
   - **Near Field Communication Tag Reading**
   - У Info.plist: `NFCReaderUsageDescription`, `NSCameraUsageDescription`, `NSMicrophoneUsageDescription`, `NSMotionUsageDescription`
4. Для NFC у entitlements: `com.apple.developer.nfc.readersession.formats` = NDEF (і Tag якщо потрібно).
5. Підключіть iPhone → Run.

Альтернатива без платного Developer: безкоштовний Apple ID, встановлення на свій тестовий телефон (сертифікат ~7 днів).

## Що тестує

| Тест | API | Примітка |
|------|-----|----------|
| NFC | CoreNFC | Піднести відомий тег / Libre |
| Вібрація | UIImpactFeedback / AudioServices | |
| Touch grid | SwiftUI | Перевірка зон екрана |
| Motion | CoreMotion | Акселерометр/гіроскоп |
| Камера | AVFoundation | Прев’ю + старт сесії |
| Мікрофон | AVAudioRecorder level | |
| Audio | AVAudioPlayer tone | Динамік |
| Мережа | NWPathMonitor | Wi‑Fi / cellular наявність |

## Експорт

Кнопка **Експорт JSON** → Share Sheet (AirDrop на ПК СЦ).  
На ПК можна покласти файл поруч із `scan_*.html` від USB-тулзи.

## Важливо

Це **не** Apple AST. Не замінює офіційну діагностику авторизованого СЦ.  
Не читає чужі дані клієнта — лише результати ваших тестів.
