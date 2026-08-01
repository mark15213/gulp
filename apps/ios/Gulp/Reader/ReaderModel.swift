import Foundation
import GulpAPI
import Observation

/// One pack, read-only (spec §2.6). Editing blocks and accepting cards stay
/// on web; this side reads and asks questions.
@Observable
@MainActor
final class ReaderModel {
    private(set) var pack: Components.Schemas.PackOut?
    private(set) var load: AppModel.Load = .idle
    private(set) var messages: [Components.Schemas.MessageOut] = []

    /// The block pulled into the conversation, shown above the composer as a
    /// removable chip so it is always clear what the question is about.
    var attachedBlockID: String?
    var draft = ""
    private(set) var isAnswering = false
    /// Tokens arriving from the stream, before they become a stored message.
    private(set) var streaming = ""

    let snapshotID: String
    private let client: Client
    private weak var auth: Auth?

    init(snapshotID: String, client: Client = GulpClientFactory.make(), auth: Auth? = nil) {
        self.snapshotID = snapshotID
        self.client = client
        self.auth = auth
    }

    func load() async {
        load = .loading
        do {
            let output = try await client.get_pack_snapshots__snapshot_id__pack_get(
                path: .init(snapshot_id: snapshotID)
            )
            switch output {
            case let .ok(response):
                pack = try response.body.json
                load = .loaded
            case let .undocumented(statusCode, _):
                if statusCode == 401 { auth?.sessionExpired() }
                load = .failed(statusCode == 404
                    ? "This one hasn't been digested yet."
                    : "Couldn't open this (\(statusCode)).")
            default:
                load = .failed("Couldn't open this.")
            }
        } catch {
            load = .failed(error.asGulpError.display)
        }
        await loadMessages()
    }

    func loadMessages() async {
        guard let output = try? await client
            .list_messages_route_snapshots__snapshot_id__messages_get(
                path: .init(snapshot_id: snapshotID)
            ),
            case let .ok(response) = output,
            let list = try? response.body.json
        else { return }
        messages = list
    }

    /// The answer streams as server-sent events.
    ///
    /// **The one place this app does not use the generated client.** The
    /// endpoint really serves `text/event-stream`, but FastAPI declares its
    /// response as `application/json`, so the generated client tries to decode
    /// the whole stream as one JSON value and fails. Repo rule 2 still holds
    /// where it matters — the request and the message type both come from the
    /// contract; only the transport for this one endpoint is hand-rolled, and
    /// it shares the same cookie store as everything else.
    ///
    /// Frames match the TypeScript client's: `data: {...}\n\n`, carrying
    /// `delta`, `done` or `error`.
    func ask() async {
        let question = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !question.isEmpty, !isAnswering else { return }
        draft = ""
        isAnswering = true
        streaming = ""

        var request = URLRequest(
            url: GulpEnvironment.baseURL
                .appendingPathComponent("snapshots")
                .appendingPathComponent(snapshotID)
                .appendingPathComponent("messages")
                .appendingPathComponent("stream")
        )
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.httpBody = try? JSONSerialization.data(withJSONObject: [
            "content": question,
            "block_refs": attachedBlockID.map { [$0] } ?? [],
        ])

        let configuration = URLSessionConfiguration.default
        configuration.httpCookieStorage = GulpClientFactory.cookies
        configuration.httpShouldSetCookies = true
        let session = URLSession(configuration: configuration)

        do {
            let (bytes, response) = try await session.bytes(for: request)
            if let http = response as? HTTPURLResponse, http.statusCode == 401 {
                auth?.sessionExpired()
                isAnswering = false
                return
            }
            for try await line in bytes.lines {
                guard line.hasPrefix("data: ") else { continue }
                let payload = Data(line.dropFirst(6).utf8)
                guard let event = try? JSONSerialization.jsonObject(with: payload)
                        as? [String: Any],
                      let type = event["type"] as? String
                else { continue }
                switch type {
                case "delta":
                    streaming += (event["text"] as? String) ?? ""
                case "error", "done":
                    break
                default:
                    break
                }
            }
        } catch {
            // The thread below is the truth; a dropped stream just means the
            // answer arrives on reload rather than as it is written.
        }

        isAnswering = false
        streaming = ""
        attachedBlockID = nil
        await loadMessages()
    }
}
