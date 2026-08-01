import Foundation
import GulpAPI
import Observation

/// Who is signed in, and the only object allowed to change that.
///
/// Auth is a cookie, not a token (spec §7.2). `POST /auth/login` sets a
/// persistent session cookie which `HTTPCookieStorage` keeps across launches,
/// so "stay signed in" needs no storage of our own — restoring is just asking
/// the server who we are.
@Observable
@MainActor
final class Auth {
    enum State: Equatable {
        /// Before the first `restore()` — show nothing rather than guessing.
        case unknown
        case signedOut
        case signedIn(Components.Schemas.UserPublic)
    }

    private(set) var state: State = .unknown
    private(set) var isWorking = false

    private let client: Client

    init(client: Client = GulpClientFactory.make()) {
        self.client = client
    }

    var user: Components.Schemas.UserPublic? {
        if case let .signedIn(user) = state { return user }
        return nil
    }

    /// Ask the server whether the stored cookie is still good.
    func restore() async {
        do {
            let user = try await me()
            state = .signedIn(user)
        } catch GulpError.unauthorized {
            state = .signedOut
        } catch {
            // Offline with a cookie we have no reason to distrust: stay
            // `unknown` so the shell can show a retry rather than bouncing a
            // signed-in user to a login form because the train went into a
            // tunnel.
            state = .unknown
        }
    }

    func signIn(email: String, password: String) async throws {
        isWorking = true
        defer { isWorking = false }

        let output = try await client.login_auth_login_post(
            body: .json(.init(email: email, password: password))
        )
        switch output {
        case let .ok(response):
            state = .signedIn(try response.body.json)
        case .unprocessableContent:
            throw GulpError.message("Check the email and password and try again.")
        case let .undocumented(statusCode, _):
            throw statusCode == 401
                ? GulpError.message("That email and password don't match.")
                : GulpError.unexpected("Sign-in failed (\(statusCode)).")
        }
    }

    func register(email: String, password: String) async throws {
        isWorking = true
        defer { isWorking = false }

        let output = try await client.register_auth_register_post(
            body: .json(.init(email: email, password: password))
        )
        switch output {
        case let .created(response):
            state = .signedIn(try response.body.json)
        case .unprocessableContent:
            throw GulpError.message("That email doesn't look right, or the password is too short.")
        case let .undocumented(statusCode, _):
            throw statusCode == 409
                ? GulpError.message("That email already has an account. Sign in instead.")
                : GulpError.unexpected("Couldn't create the account (\(statusCode)).")
        }
    }

    func signOut() async {
        _ = try? await client.logout_auth_logout_post()
        GulpClientFactory.clearCookies()
        state = .signedOut
    }

    /// Any screen that sees a 401 calls this; the shell reacts, the screen
    /// doesn't have to know what a login form is.
    func sessionExpired() {
        GulpClientFactory.clearCookies()
        state = .signedOut
    }

    private func me() async throws -> Components.Schemas.UserPublic {
        let output = try await client.me_auth_me_get()
        switch output {
        case let .ok(response):
            return try response.body.json
        case let .undocumented(statusCode, _):
            if statusCode == 401 { throw GulpError.unauthorized }
            throw GulpError.unexpected("Couldn't read your account (\(statusCode)).")
        }
    }
}
