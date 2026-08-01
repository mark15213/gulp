import Foundation
import GulpAPI
import OpenAPIRuntime
import OpenAPIURLSession

// The one place a network client is constructed. Everything above this talks
// to the *generated* client (repo rule 2) — no hand-written requests, no
// hand-written response types.

enum GulpEnvironment {
    private static let baseURLKey = "GulpBaseURL"

    /// Overridable at launch so a device can point at a LAN address or a
    /// deployment without a rebuild: `-GulpBaseURL http://10.0.0.4:8000`.
    ///
    /// A launch argument lands in the *volatile* argument domain, which only
    /// survives the launch Xcode itself performs. On a phone that is useless —
    /// the next tap on the home screen would fall back to a loopback address
    /// with nothing behind it. So the override is promoted into the persistent
    /// domain the first time it is seen: set it once from Xcode, and the app
    /// keeps talking to your Mac after that.
    static var baseURL: URL {
        let defaults = UserDefaults.standard
        guard let raw = defaults.string(forKey: baseURLKey), let url = URL(string: raw) else {
            return GulpAPI.defaultBaseURL
        }
        defaults.set(raw, forKey: baseURLKey)
        return url
    }

    /// Shared with the extension so a login in the app is a login in the share
    /// sheet (spec §7.2). The session cookie is persistent — `_set_cookie`
    /// sets `max_age`, not a session cookie — so this survives relaunches
    /// without any storage of our own.
    static let appGroup = "group.app.gulp.shared"
}

/// Python writes timestamps with `datetime.isoformat()`, which emits
/// microseconds — `2026-06-24T08:34:55.277172Z` — **except** when they happen
/// to be zero, in which case it drops the fraction entirely. The runtime's
/// stock ISO8601 transcoder accepts only one of those shapes, so half the
/// responses on this API fail to decode depending on the clock.
///
/// Accept both. Encode with the fraction, which the server always parses.
struct FlexibleISO8601: DateTranscoder {
    private static let withFraction: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private static let withoutFraction: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    func encode(_ date: Date) throws -> String {
        Self.withFraction.string(from: date)
    }

    func decode(_ dateString: String) throws -> Date {
        if let date = Self.withFraction.date(from: dateString) { return date }
        if let date = Self.withoutFraction.date(from: dateString) { return date }
        throw DecodingError.dataCorrupted(
            .init(
                codingPath: [],
                debugDescription: "Expected an ISO8601 timestamp, got \"\(dateString)\""
            )
        )
    }
}

enum GulpClientFactory {
    static let cookies: HTTPCookieStorage = {
        // Falls back to the process store when the App Group is unavailable
        // (previews, unit tests, an unsigned build).
        HTTPCookieStorage.sharedCookieStorage(
            forGroupContainerIdentifier: GulpEnvironment.appGroup
        )
    }()

    static func make(baseURL: URL? = nil) -> Client {
        let configuration = URLSessionConfiguration.default
        configuration.httpCookieStorage = cookies
        configuration.httpShouldSetCookies = true
        configuration.httpCookieAcceptPolicy = .always
        configuration.waitsForConnectivity = false
        configuration.timeoutIntervalForRequest = 20

        return Client(
            serverURL: baseURL ?? GulpEnvironment.baseURL,
            configuration: Configuration(dateTranscoder: FlexibleISO8601()),
            transport: URLSessionTransport(
                configuration: .init(session: URLSession(configuration: configuration))
            )
        )
    }

    /// Sign-out has to clear the cookie itself: the server expires it, but a
    /// stale copy in a shared store would still be sent by the extension.
    static func clearCookies() {
        cookies.cookies?.forEach(cookies.deleteCookie)
    }
}

/// What went wrong, in terms the UI can act on rather than in transport terms.
enum GulpError: Error, Equatable {
    /// The session is gone. Every screen treats this the same way.
    case unauthorized
    /// The server said no and told us why.
    case message(String)
    /// The request never landed.
    case offline
    /// Everything else, including a contract mismatch.
    case unexpected(String)

    var display: String {
        switch self {
        case .unauthorized: "Your session expired. Sign in again."
        case let .message(text): text
        case .offline: "Can't reach Gulp. Check your connection."
        case let .unexpected(text): text
        }
    }
}

extension Error {
    /// Map a transport or client error onto something a screen can show.
    var asGulpError: GulpError {
        if let gulp = self as? GulpError { return gulp }
        let nsError = self as NSError
        if nsError.domain == NSURLErrorDomain {
            switch nsError.code {
            case NSURLErrorNotConnectedToInternet,
                 NSURLErrorNetworkConnectionLost,
                 NSURLErrorCannotConnectToHost,
                 NSURLErrorTimedOut:
                return .offline
            default:
                break
            }
        }
        return .unexpected(localizedDescription)
    }
}
