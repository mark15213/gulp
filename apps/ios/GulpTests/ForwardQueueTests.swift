import Testing
import Foundation
@testable import Gulp

/// The queue is the promise that a capture is never lost. It runs in the
/// extension, which gets a few seconds inside somebody else's app and no second
/// chance — so these assertions are about survival, not about happy paths.
@Suite("Forwards that could not be sent", .serialized)
struct ForwardQueueTests {
    init() { ForwardQueue.clear() }

    @Test("A queued forward survives being written and read back")
    func roundTrip() {
        ForwardQueue.enqueue(ForwardDraft(
            url: "https://example.com/a",
            note: "worth a second look",
            tags: ["ml", "reading"]
        ))

        let pending = ForwardQueue.pending()
        #expect(pending.count == 1)
        #expect(pending.first?.url == "https://example.com/a")
        #expect(pending.first?.note == "worth a second look")
        #expect(pending.first?.tags == ["ml", "reading"])

        ForwardQueue.clear()
        #expect(ForwardQueue.pending().isEmpty)
    }

    @Test("Queueing twice keeps both, in order")
    func keepsEveryOne() {
        ForwardQueue.enqueue(ForwardDraft(url: "https://example.com/1"))
        ForwardQueue.enqueue(ForwardDraft(url: "https://example.com/2"))

        #expect(ForwardQueue.pending().map(\.url) == [
            "https://example.com/1",
            "https://example.com/2",
        ])
        ForwardQueue.clear()
    }

    @Test("Flushing an empty queue is free and does not throw")
    func emptyFlush() async {
        ForwardQueue.clear()
        let sent = await ForwardQueue.flush()
        #expect(sent == 0)
    }
}

@Suite("What a pasted string is")
struct ForwardDraftTests {
    @Test("An http address becomes a url, not text")
    func pastedLink() {
        let draft = ForwardDraft.fromPasted("  https://arxiv.org/abs/1607.06450  ")
        #expect(draft.url == "https://arxiv.org/abs/1607.06450")
        #expect(draft.text == nil)
        #expect(draft.host == "arxiv.org")
    }

    @Test("Prose stays prose, even when it mentions a domain")
    func pastedProse() {
        let draft = ForwardDraft.fromPasted("read this on arxiv.org tomorrow")
        #expect(draft.url == nil)
        #expect(draft.text == "read this on arxiv.org tomorrow")
    }

    @Test("A bare domain is text — capture decides, not the phone")
    func bareDomain() {
        let draft = ForwardDraft.fromPasted("arxiv.org")
        #expect(draft.url == nil)
        #expect(draft.text == "arxiv.org")
    }

    @Test("An empty draft knows it has nothing to send")
    func emptiness() {
        #expect(ForwardDraft().isEmpty)
        #expect(!ForwardDraft(url: "https://example.com").isEmpty)
        #expect(!ForwardDraft(text: "a thought").isEmpty)
    }

    @Test("A link with no title falls back to its host")
    func titleFallback() {
        #expect(ForwardDraft(url: "https://example.com/x").detectedTitle == "example.com")
        #expect(ForwardDraft(text: "a short note").detectedTitle == "a short note")
        #expect(ForwardDraft().detectedTitle == "Untitled")
    }
}
