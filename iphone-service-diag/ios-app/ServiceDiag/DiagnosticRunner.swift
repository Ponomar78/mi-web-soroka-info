import AVFoundation
import AudioToolbox
import CoreBluetooth
import CoreMotion
import CoreTelephony
import Foundation
import LocalAuthentication
import Network
import SwiftUI
import UIKit

enum TestKind: String, CaseIterable, Identifiable, Codable {
    case vibration, motion, speaker, earpiece, microphone
    case wifi, cellular, bluetooth, faceid, display, camera, nfc

    var id: String { rawValue }

    var title: String {
        switch self {
        case .vibration: return "Вібрація / Taptic"
        case .motion: return "Акселерометр / гіроскоп"
        case .speaker: return "Динамік (гучний)"
        case .earpiece: return "Слухавка (верх)"
        case .microphone: return "Мікрофон"
        case .wifi: return "Wi‑Fi статус"
        case .cellular: return "GSM / стільниковий"
        case .bluetooth: return "Bluetooth радіо"
        case .faceid: return "Face ID / Touch ID"
        case .display: return "Екран (touch grid)"
        case .camera: return "Камера"
        case .nfc: return "NFC (піднести тег)"
        }
    }
}

enum TestStatus: String, Codable {
    case pass, fail, skip, info

    var color: Color {
        switch self {
        case .pass: return .green
        case .fail: return .red
        case .skip: return .orange
        case .info: return .blue
        }
    }
}

struct TestResult: Identifiable, Codable {
    let id: UUID
    let kind: TestKind
    let status: TestStatus
    let detail: String
    let at: Date

    init(kind: TestKind, status: TestStatus, detail: String) {
        self.id = UUID()
        self.kind = kind
        self.status = status
        self.detail = detail
        self.at = Date()
    }
}

@MainActor
final class DiagnosticRunner: ObservableObject {
    @Published var results: [TestResult] = []
    @Published var isRunning = false
    @Published var showTouchGrid = false
    @Published var showCamera = false

    private var touchContinuation: CheckedContinuation<Bool, Never>?
    private var cameraContinuation: CheckedContinuation<(Bool, String), Never>?
    private let motion = CMMotionManager()
    private let nfc = NFCTester()
    private var btProbe: BTProbe?

    func clear() { results.removeAll() }

    func runAll(includeNFC: Bool) async {
        isRunning = true
        defer { isRunning = false }
        let kinds: [TestKind] = includeNFC
            ? TestKind.allCases
            : TestKind.allCases.filter { $0 != .nfc }
        for kind in kinds {
            await run(kind)
        }
    }

    func run(_ kind: TestKind) async {
        switch kind {
        case .vibration:
            UIImpactFeedbackGenerator(style: .heavy).impactOccurred()
            AudioServicesPlaySystemSound(kSystemSoundID_Vibrate)
            results.append(.init(kind: .vibration, status: .pass, detail: "Команда вібрації надіслана — відчуйте корпус"))
        case .motion:
            results.append(await testMotion())
        case .speaker:
            results.append(await testTone(kind: .speaker, toSpeaker: true))
        case .earpiece:
            results.append(await testTone(kind: .earpiece, toSpeaker: false))
        case .microphone:
            results.append(await testMic())
        case .wifi:
            results.append(await testPath(kind: .wifi, want: .wifi))
        case .cellular:
            results.append(await testCellular())
        case .bluetooth:
            results.append(await testBluetooth())
        case .faceid:
            results.append(testFaceID())
        case .display:
            showTouchGrid = true
            let ok = await withCheckedContinuation { (cont: CheckedContinuation<Bool, Never>) in
                touchContinuation = cont
            }
            results.append(.init(kind: .display, status: ok ? .pass : .fail, detail: ok ? "Усі зони натиснуті" : "Тест скасовано / неповний"))
        case .camera:
            showCamera = true
            let (ok, detail) = await withCheckedContinuation { (cont: CheckedContinuation<(Bool, String), Never>) in
                cameraContinuation = cont
            }
            results.append(.init(kind: .camera, status: ok ? .pass : .fail, detail: detail))
        case .nfc:
            results.append(await nfc.scanOnce())
        }
    }

    func finishTouch(ok: Bool) {
        showTouchGrid = false
        touchContinuation?.resume(returning: ok)
        touchContinuation = nil
    }

    func finishCamera(ok: Bool, detail: String) {
        showCamera = false
        cameraContinuation?.resume(returning: (ok, detail))
        cameraContinuation = nil
    }

    func exportJSON() -> String {
        let payload: [String: Any] = [
            "tool": "ServiceDiag",
            "version": "0.2.0",
            "device": UIDevice.current.model,
            "system": UIDevice.current.systemVersion,
            "results": results.map { r -> [String: String] in
                [
                    "kind": r.kind.rawValue,
                    "status": r.status.rawValue,
                    "detail": r.detail,
                    "at": ISO8601DateFormatter().string(from: r.at),
                ]
            },
            "wet_no_sound_hints": [
                "Після вологи немає звуку — часто динамік/кодек/корозія, не ПЗ",
                "Порівняйте динамік vs слухавка vs навушники",
                "З Mac зтягніть panic-full кнопкою повного скану",
            ],
        ]
        guard JSONSerialization.isValidJSONObject(payload),
              let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys]),
              let text = String(data: data, encoding: .utf8)
        else {
            return "{\"error\":\"encode failed\"}"
        }
        return text
    }

    func exportFileURL() -> URL? {
        guard !results.isEmpty else { return nil }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("ServiceDiag-\(Int(Date().timeIntervalSince1970)).json")
        do {
            try exportJSON().data(using: .utf8)?.write(to: url)
            return url
        } catch {
            return nil
        }
    }

    private func testMotion() async -> TestResult {
        guard motion.isAccelerometerAvailable else {
            return .init(kind: .motion, status: .fail, detail: "Акселерометр недоступний")
        }
        motion.accelerometerUpdateInterval = 0.1
        motion.startAccelerometerUpdates()
        try? await Task.sleep(nanoseconds: 600_000_000)
        let data = motion.accelerometerData?.acceleration
        motion.stopAccelerometerUpdates()
        guard let data else {
            return .init(kind: .motion, status: .fail, detail: "Немає даних")
        }
        let detail = String(format: "x=%.2f y=%.2f z=%.2f", data.x, data.y, data.z)
        return .init(kind: .motion, status: .pass, detail: detail)
    }

    private func testTone(kind: TestKind, toSpeaker: Bool) async -> TestResult {
        let session = AVAudioSession.sharedInstance()
        do {
            if toSpeaker {
                try session.setCategory(.playback, mode: .default, options: [.defaultToSpeaker])
            } else {
                try session.setCategory(.playAndRecord, mode: .voiceChat, options: [])
                try session.overrideOutputAudioPort(.none)
            }
            try session.setActive(true)
            AudioServicesPlaySystemSound(1005)
            try? await Task.sleep(nanoseconds: 700_000_000)
            let whereTo = toSpeaker ? "СЛУХАЙТЕ НИЖНІЙ ДИНАМІК" : "СЛУХАЙТЕ ВЕРХНЮ СЛУХАВКУ (біля Face ID)"
            return .init(kind: kind, status: .info, detail: "Тон відтворено — \(whereTo). Позначте самі: чути/не чути.")
        } catch {
            return .init(kind: kind, status: .fail, detail: error.localizedDescription)
        }
    }

    private func testMic() async -> TestResult {
        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker])
            try session.setActive(true)
            let permission = await withCheckedContinuation { (cont: CheckedContinuation<Bool, Never>) in
                session.requestRecordPermission { cont.resume(returning: $0) }
            }
            guard permission else {
                return .init(kind: .microphone, status: .fail, detail: "Немає дозволу на мікрофон")
            }
            return .init(kind: .microphone, status: .pass, detail: "Дозвіл OK, сесія активна — говоріть і дивіться індикатор виклику/диктофон")
        } catch {
            return .init(kind: .microphone, status: .fail, detail: error.localizedDescription)
        }
    }

    private func testPath(kind: TestKind, want: NWInterface.InterfaceType) async -> TestResult {
        await withCheckedContinuation { cont in
            let monitor = NWPathMonitor()
            let queue = DispatchQueue(label: "net.monitor.\(kind.rawValue)")
            monitor.pathUpdateHandler = { path in
                monitor.cancel()
                let uses = path.usesInterfaceType(want)
                let detail = "status=\(path.status == .satisfied ? "ok" : "down"), \(want)=\(uses)"
                cont.resume(returning: .init(kind: kind, status: uses ? .pass : .fail, detail: detail))
            }
            monitor.start(queue: queue)
        }
    }

    private func testCellular() async -> TestResult {
        let info = CTTelephonyNetworkInfo()
        let tech = info.serviceCurrentRadioAccessTechnology?.values.first
        let carriers = info.serviceSubscriberCellularProviders?.values.compactMap { $0.carrierName }.joined(separator: ",")
        var parts: [String] = []
        if let carriers, !carriers.isEmpty { parts.append("operator=\(carriers)") } else { parts.append("operator=?") }
        if let tech { parts.append("rat=\(tech)") } else { parts.append("rat=none") }
        let path = await testPath(kind: .cellular, want: .cellular)
        return .init(
            kind: .cellular,
            status: path.status,
            detail: parts.joined(separator: ", ") + "; " + path.detail
        )
    }

    private func testBluetooth() async -> TestResult {
        await withCheckedContinuation { cont in
            let probe = BTProbe { state in
                let detail: String
                let status: TestStatus
                switch state {
                case .poweredOn:
                    detail = "Bluetooth ON (радіо відповідає)"
                    status = .pass
                case .poweredOff:
                    detail = "Bluetooth OFF у налаштуваннях — увімкніть і повторіть"
                    status = .fail
                case .unauthorized:
                    detail = "Немає дозволу Bluetooth для апки"
                    status = .fail
                case .unsupported:
                    detail = "BT не підтримується (?)"
                    status = .fail
                default:
                    detail = "Стан BT: \(state.rawValue)"
                    status = .info
                }
                cont.resume(returning: .init(kind: .bluetooth, status: status, detail: detail))
            }
            self.btProbe = probe
            probe.start()
        }
    }

    private func testFaceID() -> TestResult {
        let ctx = LAContext()
        var err: NSError?
        let ok = ctx.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &err)
        let type: String
        switch ctx.biometryType {
        case .faceID: type = "Face ID"
        case .touchID: type = "Touch ID"
        case .opticID: type = "Optic ID"
        default: type = "немає біометрії"
        }
        if ok {
            return .init(kind: .faceid, status: .pass, detail: "\(type) доступний системі (не повний калібрувальний тест Apple)")
        }
        return .init(kind: .faceid, status: .fail, detail: "\(type): \(err?.localizedDescription ?? "недоступно")")
    }
}

/// Minimal CoreBluetooth power-state probe.
final class BTProbe: NSObject, CBCentralManagerDelegate {
    private var manager: CBCentralManager?
    private let onState: (CBManagerState) -> Void
    private var sent = false

    init(onState: @escaping (CBManagerState) -> Void) {
        self.onState = onState
    }

    func start() {
        manager = CBCentralManager(delegate: self, queue: .main, options: [CBCentralManagerOptionShowPowerAlertKey: true])
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        guard !sent else { return }
        sent = true
        onState(central.state)
    }
}
