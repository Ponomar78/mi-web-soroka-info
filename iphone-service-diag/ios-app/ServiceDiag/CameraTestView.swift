import AVFoundation
import SwiftUI

struct CameraTestView: View {
    let onDone: (Bool, String) -> Void
    @StateObject private var model = CameraModel()

    var body: some View {
        NavigationStack {
            ZStack {
                if model.permissionGranted {
                    CameraPreview(session: model.session)
                        .ignoresSafeArea()
                } else {
                    Text(model.statusText)
                        .padding()
                }
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Скасувати") {
                        model.stop()
                        onDone(false, "Скасовано")
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Камера OK") {
                        model.stop()
                        onDone(true, model.statusText)
                    }
                    .disabled(!model.permissionGranted || !model.running)
                }
            }
            .task { await model.start() }
        }
    }
}

final class CameraModel: ObservableObject {
    let session = AVCaptureSession()
    @Published var permissionGranted = false
    @Published var running = false
    @Published var statusText = "Запит доступу до камери…"

    @MainActor
    func start() async {
        let granted: Bool
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            granted = true
        case .notDetermined:
            granted = await AVCaptureDevice.requestAccess(for: .video)
        default:
            granted = false
        }
        permissionGranted = granted
        guard granted else {
            statusText = "Немає дозволу на камеру"
            return
        }
        session.beginConfiguration()
        session.sessionPreset = .medium
        defer { session.commitConfiguration() }
        guard
            let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
            let input = try? AVCaptureDeviceInput(device: device),
            session.canAddInput(input)
        else {
            statusText = "Не вдалося відкрити задню камеру"
            return
        }
        session.inputs.forEach { session.removeInput($0) }
        session.addInput(input)
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.session.startRunning()
            DispatchQueue.main.async {
                self?.running = true
                self?.statusText = "Прев'ю задньої камери активне"
            }
        }
    }

    func stop() {
        session.stopRunning()
        running = false
    }
}

struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession

    func makeUIView(context: Context) -> UIView {
        let view = PreviewView()
        view.previewLayer.session = session
        view.previewLayer.videoGravity = .resizeAspectFill
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {}

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }
}
