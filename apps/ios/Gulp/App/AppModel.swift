import Foundation
import GulpAPI
import Observation

/// The state the shell owns: what the server last told us, and whether a
/// session is running. Screens **observe** this and never fetch in `body`
/// (plan Task 3) — a view that starts its own request re-runs it every time
/// SwiftUI re-evaluates, which is not a schedule anyone chose.
@Observable
@MainActor
final class AppModel {
    enum Load: Equatable, Sendable {
        case idle
        case loading
        case failed(String)
        case loaded
    }

    private(set) var today: Components.Schemas.TodayOut?
    private(set) var todayLoad: Load = .idle

    private(set) var library: [Components.Schemas.SnapshotOut] = []
    private(set) var libraryLoad: Load = .idle

    /// How long a session should be. There is no endpoint to persist this —
    /// `UserPublic.gulp_session_minutes` is read-only over the API — but
    /// `POST /sessions` takes `target_minutes` per session, so the preference
    /// is honoured even though it does not sync to web.
    var sessionMinutes: Int {
        get { UserDefaults.standard.object(forKey: "sessionMinutes") as? Int ?? 5 }
        set { UserDefaults.standard.set(newValue, forKey: "sessionMinutes") }
    }

    /// A running session takes the whole screen — no tab bar, one thing at a
    /// time (`03 §7.7`). Task 5 fills it in.
    var sessionIsRunning = false

    /// The snapshot being read, if any. Task 8 fills it in.
    var readingSnapshotID: String?

    private let client: Client
    private weak var auth: Auth?

    init(client: Client = GulpClientFactory.make()) {
        self.client = client
    }

    /// The shell hands us auth so a 401 anywhere lands in one place instead of
    /// every screen learning what a login form is.
    func attach(auth: Auth) {
        self.auth = auth
    }

    /// Anything the share extension could not send — offline, or a login that
    /// had expired by the time you shared — is waiting in the App Group queue.
    /// The app is the only process that gets a second chance, so it takes it
    /// on every launch before asking what is due.
    func flushPendingForwards() async {
        let sent = await ForwardQueue.flush(client: client)
        if sent > 0 { await refreshToday() }
    }

    func refreshToday() async {
        if todayLoad == .idle { todayLoad = .loading }
        do {
            let output = try await client.get_today_today_get()
            switch output {
            case let .ok(response):
                today = try response.body.json
                todayLoad = .loaded
            case let .undocumented(statusCode, _):
                try handle(statusCode: statusCode)
                todayLoad = .failed("Couldn't load today (\(statusCode)).")
            }
        } catch {
            let gulp = error.asGulpError
            if case .unauthorized = gulp { auth?.sessionExpired() }
            // Keep whatever we already had on screen; a failed refresh should
            // not blank a screen that was fine a second ago.
            todayLoad = today == nil ? .failed(gulp.display) : .loaded
        }
    }

    /// Fire the pack pipeline for something forwarded on the move. One tap
    /// that starts an existing pipeline is not curation (spec §2.1), and it
    /// needs no server work — the endpoint already exists.
    func startProcessing(_ snapshotID: String) async {
        // Optimistic: the row flips to `processing` immediately, because the
        // request is a hand-off and waiting on it teaches the wrong thing
        // about what the button did.
        setStatus(.processing, for: snapshotID)
        do {
            _ = try await client.process_snapshot_endpoint_snapshots__snapshot_id__process_post(
                path: .init(snapshot_id: snapshotID)
            )
            await refreshToday()
        } catch {
            let gulp = error.asGulpError
            if case .unauthorized = gulp { auth?.sessionExpired() }
            setStatus(.unprocessed, for: snapshotID)
            todayLoad = .failed(gulp.display)
        }
    }

    private func setStatus(
        _ status: Components.Schemas.SnapshotStatus,
        for snapshotID: String
    ) {
        guard var today, let index = today.recent.firstIndex(where: { $0.id == snapshotID })
        else { return }
        today.recent[index].status = status
        self.today = today
    }

    func refreshLibrary() async {
        if libraryLoad == .idle { libraryLoad = .loading }
        do {
            let output = try await client.get_library_library_get()
            switch output {
            case let .ok(response):
                library = try response.body.json.items
                libraryLoad = .loaded
            case let .undocumented(statusCode, _):
                try handle(statusCode: statusCode)
                libraryLoad = .failed("Couldn't read your library (\(statusCode)).")
            }
        } catch {
            let gulp = error.asGulpError
            if case .unauthorized = gulp { auth?.sessionExpired() }
            libraryLoad = library.isEmpty ? .failed(gulp.display) : .loaded
        }
    }

    private func handle(statusCode: Int) throws {
        if statusCode == 401 {
            auth?.sessionExpired()
            throw GulpError.unauthorized
        }
    }
}
