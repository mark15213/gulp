import Foundation
import GulpAPI
import Observation

/// One run of the daily loop: present a card, take a grade, move on.
///
/// `SessionOut.cards` ships `answer` and `explanation` up front, so revealing
/// is local — no round trip in the middle of a session, and the only network
/// call per card is the grade going out (spec §2.2).
@Observable
@MainActor
final class SessionModel {
    enum Phase: Equatable {
        case building
        case prompt
        case revealed
        case complete
        case failed(String)
    }

    private(set) var phase: Phase = .building
    private(set) var cards: [Components.Schemas.SessionCardOut] = []
    private(set) var index = 0
    private(set) var summary: Components.Schemas.SummaryOut?

    /// What the last grade earned, shown under the buttons so the scheduler
    /// stops being invisible.
    private(set) var intervals: [Grade: String] = [:]

    /// The answer the user picked, for an mcq, or typed, for the rest.
    var selection: String?
    var typed = ""

    enum Grade: String, CaseIterable {
        case missed, fuzzy, gotIt

        var label: String {
            switch self {
            case .missed: "Missed"
            case .fuzzy: "Fuzzy"
            case .gotIt: "Got it"
            }
        }

        var wire: Components.Schemas.ReviewIn.gradePayload {
            switch self {
            case .missed: .missed
            case .fuzzy: .fuzzy
            case .gotIt: .got_it
            }
        }
    }

    private var sessionID: String?
    private let client: Client
    private weak var auth: Auth?

    init(client: Client = GulpClientFactory.make(), auth: Auth? = nil) {
        self.client = client
        self.auth = auth
    }

    var card: Components.Schemas.SessionCardOut? {
        index < cards.count ? cards[index] : nil
    }

    var total: Int { cards.count }

    func start(targetMinutes: Int?) async {
        phase = .building
        do {
            // Resume rather than stack a second session on the first.
            if let existing = try await currentSession() {
                adopt(existing)
                return
            }
            let output = try await client.start_session_gulp_sessions_post(
                body: .json(.init(scope_type: .daily, target_minutes: targetMinutes))
            )
            switch output {
            case let .ok(response):
                adopt(try response.body.json)
            case .unprocessableContent:
                phase = .failed("Couldn't build a session from what's due.")
            case let .undocumented(statusCode, _):
                try reject(statusCode)
                phase = .failed("Couldn't start a session (\(statusCode)).")
            }
        } catch {
            fail(error)
        }
    }

    func grade(_ grade: Grade) async {
        guard let sessionID, let card else { return }
        do {
            let output = try await client.review_gulp_sessions__session_id__reviews_post(
                path: .init(session_id: sessionID),
                body: .json(.init(
                    card_id: card.id,
                    grade: grade.wire,
                    response: selection ?? (typed.isEmpty ? nil : typed)
                ))
            )
            switch output {
            case let .ok(response):
                let review = try response.body.json
                if review.done {
                    await complete()
                } else {
                    advance()
                }
            case .unprocessableContent:
                phase = .failed("That grade didn't take. Try again.")
            case let .undocumented(statusCode, _):
                try reject(statusCode)
                phase = .failed("Couldn't record that (\(statusCode)).")
            }
        } catch {
            fail(error)
        }
    }

    func snooze() async {
        guard let sessionID, let card else { return }
        _ = try? await client.snooze_gulp_sessions__session_id__snooze_post(
            path: .init(session_id: sessionID),
            body: .json(.init(card_id: card.id))
        )
        advance()
    }

    func reveal() {
        guard phase == .prompt else { return }
        phase = .revealed
    }

    private func complete() async {
        guard let sessionID else { return }
        do {
            let output = try await client.complete_gulp_sessions__session_id__complete_post(
                path: .init(session_id: sessionID)
            )
            if case let .ok(response) = output {
                summary = try response.body.json
            }
            phase = .complete
        } catch {
            // The grades are already recorded; a failed summary should not
            // look like a failed session.
            phase = .complete
        }
    }

    private func advance() {
        selection = nil
        typed = ""
        index += 1
        phase = index < cards.count ? .prompt : .complete
        if phase == .complete { Task { await complete() } }
    }

    private func adopt(_ session: Components.Schemas.SessionOut) {
        sessionID = session.id
        cards = session.cards
        index = 0
        phase = cards.isEmpty ? .complete : .prompt
    }

    private func currentSession() async throws -> Components.Schemas.SessionOut? {
        do {
            let output = try await client.get_current_gulp_sessions_current_get()
            if case let .ok(response) = output {
                return try response.body.json
            }
            return nil
        } catch {
            // `GET /gulp/sessions/current` answers a literal `null` body when
            // nothing is running, and OpenAPI cannot express an optional body,
            // so the generated client fails to decode it. Treat that as "no
            // session" — see openapi_for_swift.py. A 204 here would remove the
            // wart for every typed client.
            if (error as NSError).domain == NSURLErrorDomain { throw error }
            return nil
        }
    }

    private func reject(_ statusCode: Int) throws {
        if statusCode == 401 {
            auth?.sessionExpired()
            throw GulpError.unauthorized
        }
    }

    private func fail(_ error: Error) {
        let gulp = error.asGulpError
        if case .unauthorized = gulp { auth?.sessionExpired() }
        phase = .failed(gulp.display)
    }
}
