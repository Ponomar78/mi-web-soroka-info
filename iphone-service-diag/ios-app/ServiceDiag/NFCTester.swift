import CoreNFC
import Foundation

/// One-shot NFC NDEF/tag presence test for service bench.
final class NFCTester: NSObject, NFCNDEFReaderSessionDelegate {
    private var session: NFCNDEFReaderSession?
    private var continuation: CheckedContinuation<TestResult, Never>?

    @MainActor
    func scanOnce() async -> TestResult {
        guard NFCNDEFReaderSession.readingAvailable else {
            return TestResult(
                kind: .nfc,
                status: .fail,
                detail: "NFC читання недоступне на цьому пристрої / iOS"
            )
        }
        return await withCheckedContinuation { cont in
            self.continuation = cont
            let session = NFCNDEFReaderSession(delegate: self, queue: nil, invalidateAfterFirstRead: true)
            session.alertMessage = "Піднесіть NFC-тег або глюкозний сенсор до верхньої частини iPhone"
            self.session = session
            session.begin()
        }
    }

    func readerSession(_ session: NFCNDEFReaderSession, didInvalidateWithError error: Error) {
        let ns = error as NSError
        // User cancel
        if ns.domain == NFCReaderError.errorDomain,
           ns.code == NFCReaderError.readerSessionInvalidationErrorUserCanceled.rawValue {
            finish(.init(kind: .nfc, status: .skip, detail: "Скасовано користувачем"))
            return
        }
        // Sometimes success path also invalidates; only fail if no result yet
        if continuation != nil {
            finish(.init(kind: .nfc, status: .fail, detail: error.localizedDescription))
        }
    }

    func readerSession(_ session: NFCNDEFReaderSession, didDetectNDEFs messages: [NFCNDEFMessage]) {
        let count = messages.reduce(0) { $0 + $1.records.count }
        finish(.init(
            kind: .nfc,
            status: .pass,
            detail: "NDEF OK, повідомлень=\(messages.count), записів=\(count). NFC антена/контролер відповідають."
        ))
    }

    private func finish(_ result: TestResult) {
        session = nil
        continuation?.resume(returning: result)
        continuation = nil
    }
}
