import AVFoundation
import AudioToolbox
import CoreMotion
import Foundation
import Network
import SwiftUI
import UIKit

enum TestKind: String, CaseIterable, Identifiable, Codable {
    case vibration, motion, audio, microphone, network, display, camera, nfc

    var id: String { rawValue }

    var title: String {
        switch self {
        case .vibration: return "Вібрація / Taptic"
        case .motion: return "Акселерометр / гіроскоп"
        case .audio: return "Динамік (тон)"
        case .microphone: return "Мікрофон"
        case .network: return "Мережа"
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
        case .audio:
            results.append(await testTone())
        case .microphone:
            results.append(await testMic())
        case .network:
            results.append(await testNetwork())
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
            let r = await nfc.scanOnce()
            results.append(r)
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
            "version": "0.1.0",
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

    private func testTone() async -> TestResult {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("tone.wav")
        // Short generated silence+beep via system sound as fallback
        AudioServicesPlaySystemSound(1005)
        try? await Task.sleep(nanoseconds: 400_000_000)
        _ = url
        return .init(kind: .audio, status: .pass, detail: "Системний звук відтворено — слухайте динамік")
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
            return .init(kind: .microphone, status: .pass, detail: "Дозвіл OK, сесія активна")
        } catch {
            return .init(kind: .microphone, status: .fail, detail: error.localizedDescription)
        }
    }

    private func testNetwork() async -> TestResult {
        await withCheckedContinuation { cont in
            let monitor = NWPathMonitor()
            let queue = DispatchQueue(label: "net.monitor")
            monitor.pathUpdateHandler = { path in
                monitor.cancel()
                var parts: [String] = []
                if path.status == .satisfied { parts.append("online") } else { parts.append("offline") }
                if path.usesInterfaceType(.wifi) { parts.append("wifi") }
                if path.usesInterfaceType(.cellular) { parts.append("cellular") }
                if path.usesInterfaceType(.wiredEthernet) { parts.append("ethernet") }
                let ok = path.status == .satisfied
                cont.resume(returning: .init(kind: .network, status: ok ? .pass : .fail, detail: parts.joined(separator: ", ")))
            }
            monitor.start(queue: queue)
        }
    }
}
