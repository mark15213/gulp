import Foundation
import GulpAPI

/// Captures that never reached the server.
///
/// The extension is the reason this exists: it runs for a few seconds inside
/// somebody else's app, with no way to retry later and nowhere of its own to
/// keep anything. So a forward that fails — offline, or a session that expired
/// while the phone was in a pocket — is written to the **App Group** container
/// and flushed by the app on its next launch. Capture never blocks on the
/// network, and never silently loses what you sent (`01 §10.3`, plan Task 9).
enum ForwardQueue {
    private static let filename = "pending-forwards.json"

    private static var fileURL: URL? {
        let container = FileManager.default.containerURL(
            forSecurityApplicationGroupIdentifier: GulpEnvironment.appGroup
        )
        // Unsigned builds and previews have no group container. Falling back to
        // the process's own Application Support keeps this usable in tests; it
        // just is not shared with anybody.
        let base = container ?? FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first
        return base?.appendingPathComponent(filename)
    }

    static func pending() -> [ForwardDraft] {
        guard let fileURL, let data = try? Data(contentsOf: fileURL) else { return [] }
        return (try? JSONDecoder().decode([ForwardDraft].self, from: data)) ?? []
    }

    static func enqueue(_ draft: ForwardDraft) {
        guard let fileURL else { return }
        var queue = pending()
        queue.append(draft)
        guard let data = try? JSONEncoder().encode(queue) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }

    static func clear() {
        guard let fileURL else { return }
        try? FileManager.default.removeItem(at: fileURL)
    }

    private static func replace(with queue: [ForwardDraft]) {
        guard let fileURL else { return }
        if queue.isEmpty {
            clear()
        } else if let data = try? JSONEncoder().encode(queue) {
            try? data.write(to: fileURL, options: .atomic)
        }
    }

    /// Send everything waiting. Anything that fails again stays queued — this
    /// is called on every launch, so there is always a next attempt.
    /// Returns how many got through.
    @discardableResult
    static func flush(client: Client = GulpClientFactory.make()) async -> Int {
        let queue = pending()
        guard !queue.isEmpty else { return 0 }

        var stillPending: [ForwardDraft] = []
        var sent = 0
        for draft in queue {
            if await ForwardService.send(draft, client: client) {
                sent += 1
            } else {
                stillPending.append(draft)
            }
        }
        replace(with: stillPending)
        return sent
    }
}

/// The one place `POST /capture` is called from, so the extension and the app
/// cannot drift on what a forward is.
enum ForwardService {
    enum Outcome: Equatable {
        case sent
        /// Kept for later — the caller should say so rather than show an error.
        case queued
        /// The server refused for a reason the person can act on.
        case refused(String)
    }

    /// Fire and report. A transport failure or a `401` queues rather than
    /// fails: the capture is already the user's, and losing it to a flaky
    /// network would be the one unforgivable bug in this app.
    static func forward(_ draft: ForwardDraft, client: Client = GulpClientFactory.make()) async -> Outcome {
        do {
            let output = try await client.capture_capture_post(
                body: .json(.init(
                    url: draft.url,
                    text: draft.url == nil ? draft.text : nil,
                    note: draft.note,
                    title: draft.url == nil ? nil : draft.title,
                    tags: draft.tags.isEmpty ? nil : draft.tags
                ))
            )
            switch output {
            case .ok:
                return .sent
            case let .undocumented(statusCode, _):
                if statusCode == 401 {
                    ForwardQueue.enqueue(draft)
                    return .queued
                }
                return .refused("Couldn't forward that (\(statusCode)).")
            default:
                return .refused("Couldn't forward that.")
            }
        } catch {
            // Every throw here is a transport failure — the request never
            // landed, so there is nothing to be sorry about and nothing to
            // report. Keep it and move on.
            ForwardQueue.enqueue(draft)
            return .queued
        }
    }

    /// The flush path: no queueing on failure, because the draft is already in
    /// the queue and re-adding it would duplicate the capture.
    static func send(_ draft: ForwardDraft, client: Client) async -> Bool {
        do {
            let output = try await client.capture_capture_post(
                body: .json(.init(
                    url: draft.url,
                    text: draft.url == nil ? draft.text : nil,
                    note: draft.note,
                    title: draft.url == nil ? nil : draft.title,
                    tags: draft.tags.isEmpty ? nil : draft.tags
                ))
            )
            if case .ok = output { return true }
            return false
        } catch {
            return false
        }
    }
}
