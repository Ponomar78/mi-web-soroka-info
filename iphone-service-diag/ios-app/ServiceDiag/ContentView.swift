import SwiftUI

struct ContentView: View {
    @StateObject private var runner = DiagnosticRunner()

    var body: some View {
        NavigationStack {
            List {
                Section("Швидкі дії") {
                    Button("Повний тест (без NFC)") {
                        Task { await runner.runAll(includeNFC: false) }
                    }
                    .disabled(runner.isRunning)

                    Button("Повний тест + NFC") {
                        Task { await runner.runAll(includeNFC: true) }
                    }
                    .disabled(runner.isRunning)

                    if runner.isRunning {
                        ProgressView("Йде тест…")
                    }
                }

                Section("Окремі тести") {
                    ForEach(TestKind.allCases) { kind in
                        Button(kind.title) {
                            Task { await runner.run(kind) }
                        }
                        .disabled(runner.isRunning)
                    }
                }

                Section("Результати") {
                    ForEach(runner.results) { item in
                        HStack {
                            Circle()
                                .fill(item.status.color)
                                .frame(width: 10, height: 10)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.kind.title).font(.headline)
                                Text(item.detail)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                    if runner.results.isEmpty {
                        Text("Ще немає результатів").foregroundStyle(.secondary)
                    }
                }

                Section {
                    if let url = runner.exportFileURL() {
                        ShareLink(item: url) {
                            Label("Експорт JSON", systemImage: "square.and.arrow.up")
                        }
                    } else {
                        Text("Немає даних для експорту").foregroundStyle(.secondary)
                    }

                    Button("Очистити", role: .destructive) {
                        runner.clear()
                    }
                }
            }
            .navigationTitle("ServiceDiag")
        }
        .sheet(isPresented: $runner.showTouchGrid) {
            TouchGridView { ok in
                runner.finishTouch(ok: ok)
            }
        }
        .sheet(isPresented: $runner.showCamera) {
            CameraTestView { ok, detail in
                runner.finishCamera(ok: ok, detail: detail)
            }
        }
    }
}

#Preview {
    ContentView()
}
