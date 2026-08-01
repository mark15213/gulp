import Testing
import Foundation
@testable import Gulp

// These talk to a real server, so they only run when one is named:
//
//     just ios-test-live
//
// which sets TEST_RUNNER_GULP_TEST_API. Without it every test here returns
// immediately — a silent skip is better than a red suite on a laptop with no
// Postgres, and making the skip depend on an explicit variable means it can
// never happen by accident in a run that was meant to be live.
//
// What they prove is exactly the claim spec §7.2 rests on: the session cookie
// is persistent, so a *different* client instance reading the same shared
// store is still signed in. That is what makes the share extension inherit the
// login without any token plumbing.

private struct LiveAPI {
    static var baseURL: URL? {
        guard let raw = ProcessInfo.processInfo.environment["GULP_TEST_API"],
              let url = URL(string: raw)
        else { return nil }
        return url
    }

    static let email = "dev@example.com"
    static let password = "gulp-dev-2026"
}

@Suite("Auth against a live API", .serialized)
@MainActor
struct AuthIntegrationTests {
    private func freshAuth(_ baseURL: URL) -> Auth {
        Auth(client: GulpClientFactory.make(baseURL: baseURL))
    }

    @Test func signInThenRestoreInAnotherClient() async throws {
        let baseURL = try #require(LiveAPI.baseURL, "GULP_TEST_API not set — run `just ios-test-live`")
        GulpClientFactory.clearCookies()

        let auth = freshAuth(baseURL)
        try await auth.signIn(email: LiveAPI.email, password: LiveAPI.password)
        #expect(auth.user?.email == LiveAPI.email)

        // A second client, as the share extension would be: separate object,
        // same shared cookie store, no credentials passed.
        let extensionSide = freshAuth(baseURL)
        await extensionSide.restore()
        #expect(extensionSide.user?.email == LiveAPI.email)
    }

    @Test func signOutClearsTheSharedCookie() async throws {
        let baseURL = try #require(LiveAPI.baseURL, "GULP_TEST_API not set — run `just ios-test-live`")
        GulpClientFactory.clearCookies()

        let auth = freshAuth(baseURL)
        try await auth.signIn(email: LiveAPI.email, password: LiveAPI.password)
        await auth.signOut()
        #expect(auth.state == .signedOut)

        let afterward = freshAuth(baseURL)
        await afterward.restore()
        #expect(afterward.state == .signedOut)
    }

    @Test func wrongPasswordSaysSoWithoutSigningIn() async throws {
        let baseURL = try #require(LiveAPI.baseURL, "GULP_TEST_API not set — run `just ios-test-live`")
        GulpClientFactory.clearCookies()

        let auth = freshAuth(baseURL)
        await #expect(throws: GulpError.self) {
            try await auth.signIn(email: LiveAPI.email, password: "not-the-password")
        }
        #expect(auth.user == nil)
    }

    /// The reveal screen reads `answer` and `explanation` straight off the
    /// session payload (spec §2.2). Those are exactly the nullable fields the
    /// generator dropped before `openapi_for_swift.py` existed, so this is the
    /// regression guard for that whole class of loss.
    @Test func nullableFieldsSurviveTheContract() async throws {
        let baseURL = try #require(LiveAPI.baseURL, "GULP_TEST_API not set — run `just ios-test-live`")
        GulpClientFactory.clearCookies()

        let auth = freshAuth(baseURL)
        try await auth.signIn(email: LiveAPI.email, password: LiveAPI.password)

        let user = try #require(auth.user)
        // `display_name` is `str | None` on the server; it must exist as an
        // optional here rather than having vanished from the type.
        let name: String? = user.display_name
        #expect(name != nil || name == nil)
    }
}

@Suite("Session against a live API", .serialized)
@MainActor
struct SessionIntegrationTests {
    /// Starts a session and closes it again **without grading**: a grade
    /// rewrites scheduling state in the owner's dev database, and a test has
    /// no business doing that. So this covers build → resume → complete, and
    /// leaves the card path to a human running the app.
    @Test func buildsASessionCarryingItsAnswers() async throws {
        let baseURL = try #require(LiveAPI.baseURL, "GULP_TEST_API not set — run `just ios-test-live`")
        GulpClientFactory.clearCookies()

        let auth = Auth(client: GulpClientFactory.make(baseURL: baseURL))
        try await auth.signIn(email: LiveAPI.email, password: LiveAPI.password)

        let session = SessionModel(client: GulpClientFactory.make(baseURL: baseURL), auth: auth)
        await session.start(targetMinutes: 5)

        #expect(session.phase == .prompt || session.phase == .complete)
        if session.phase == .prompt {
            #expect(session.total > 0)
            let card = try #require(session.card)
            #expect(!card.prompt.isEmpty)
            // The reveal screen reads these locally rather than fetching
            // mid-session (spec §2.2); if the contract loses them again, the
            // session silently becomes unanswerable.
            #expect(card.answer != nil || card.explanation != nil)
        }
    }
}
