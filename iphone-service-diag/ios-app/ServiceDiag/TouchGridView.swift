import SwiftUI

/// Simple touch coverage grid for dead-pixel / dead-zone checks.
struct TouchGridView: View {
    let onDone: (Bool) -> Void
    private let cols = 4
    private let rows = 6
    @State private var hit: Set<Int> = []

    private var total: Int { cols * rows }

    var body: some View {
        NavigationStack {
            VStack(spacing: 8) {
                Text("Натисніть усі клітинки")
                    .font(.headline)
                Text("\(hit.count)/\(total)")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                GeometryReader { geo in
                    let w = geo.size.width / CGFloat(cols)
                    let h = geo.size.height / CGFloat(rows)
                    ForEach(0..<total, id: \.self) { i in
                        let c = i % cols
                        let r = i / cols
                        Rectangle()
                            .fill(hit.contains(i) ? Color.green.opacity(0.7) : Color.gray.opacity(0.25))
                            .border(Color.primary.opacity(0.2))
                            .frame(width: w, height: h)
                            .position(x: w * CGFloat(c) + w / 2, y: h * CGFloat(r) + h / 2)
                            .onTapGesture { hit.insert(i) }
                    }
                }
                .padding(4)
            }
            .padding()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Скасувати") { onDone(false) }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Готово") { onDone(hit.count == total) }
                        .disabled(hit.count != total)
                }
            }
        }
    }
}
