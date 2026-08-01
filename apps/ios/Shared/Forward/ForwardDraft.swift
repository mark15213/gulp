import Foundation

/// One thing on its way in. Shared because it is produced in two places — the
/// share extension and the app's own `+` — and consumed in two more: the
/// `POST /capture` call, and the on-disk queue when that call cannot happen.
struct ForwardDraft: Codable, Equatable {
    var url: String?
    var text: String?
    var note: String?
    var title: String?
    var tags: [String] = []

    /// Best guess at what to show as the headline before the server has said
    /// anything. A link with no text falls back to its host.
    var detectedTitle: String {
        if let title, !title.isEmpty { return title }
        if let text, !text.isEmpty, text.count < 120 { return text }
        if let host { return host }
        return "Untitled"
    }

    var host: String? {
        guard let url else { return nil }
        return URL(string: url)?.host()
    }

    var isEmpty: Bool {
        (url?.isEmpty ?? true) && (text?.isEmpty ?? true)
    }

    /// A pasted string is a link if it parses as one with a host, and prose
    /// otherwise — the same rule capture uses server-side.
    static func fromPasted(_ raw: String) -> ForwardDraft {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if let url = URL(string: trimmed), url.host() != nil,
           trimmed.lowercased().hasPrefix("http") {
            return ForwardDraft(url: trimmed)
        }
        return ForwardDraft(text: trimmed)
    }
}
