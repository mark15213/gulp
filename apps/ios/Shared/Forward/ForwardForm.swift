import SwiftUI

/// The forward card, shared by the share extension and the app's own `+`.
///
/// The verb is **Forward**, never Gulp — forwarding is how things get in,
/// gulping is what you do with them later (spec §2.3). The two hosts differ in
/// exactly two ways, both passed in: the extension arrives with a payload and
/// self-confirms after a moment, the app arrives empty and waits to be typed
/// into.
struct ForwardForm: View {
    let draft: ForwardDraft
    /// The extension confirms itself so a forward is one gesture. In the app
    /// you opened this on purpose, so nothing happens until you say so.
    var autoConfirmAfter: Int?
    let finish: () -> Void

    @State private var pasted = ""
    @State private var note = ""
    @State private var tags = ""
    @State private var countdown = 0
    @State private var delivery: Delivery = .waiting
    @State private var timer: Task<Void, Never>?
    @FocusState private var pasteFocused: Bool

    /// Deliberately not named `State`: the nested type would shadow SwiftUI's
    /// `@State`, the same way `Tab` shadows the tab builder.
    private enum Delivery: Equatable {
        case waiting, sending, sent, queued, failed(String)
    }

    private var composed: ForwardDraft {
        var out = draft
        if out.isEmpty, !pasted.isEmpty {
            out = ForwardDraft.fromPasted(pasted)
        }
        out.note = note.isEmpty ? nil : note
        out.title = out.url == nil ? nil : out.detectedTitle
        out.tags = tags
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        return out
    }

    private var canSend: Bool { !composed.isEmpty }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Forward to Gulp").gulpLabel()

            if draft.isEmpty {
                // The app's path: nothing was handed over, so ask for it.
                GulpField(placeholder: "Paste a link, or some text", text: $pasted)
                    .padding(.top, Space.x3)
                    .focused($pasteFocused)
            } else {
                Text(draft.detectedTitle)
                    .font(GulpFont.titleS)
                    .foregroundStyle(Ink.primary)
                    .lineLimit(2)
                    .padding(.top, Space.x3)
                if let host = draft.host {
                    Text(host).gulpLabel().padding(.top, Space.x2)
                }
            }

            if delivery == .waiting {
                GulpField(placeholder: "Add a note", text: $note)
                    .padding(.top, Space.x4)
                    .onChange(of: note) { _, _ in stopCountdown() }
                GulpField(placeholder: "Tags", text: $tags)
                    .padding(.top, Space.x2)
                    .onChange(of: tags) { _, _ in stopCountdown() }
            }

            switch delivery {
            case .waiting:
                PrimaryButton(title: "Forward") { send() }
                    .padding(.top, Space.x4)
                    .opacity(canSend ? 1 : 0.4)
                    .disabled(!canSend)
                if countdown > 0 {
                    HStack(spacing: Space.x2) {
                        Image(systemName: "clock").font(.system(size: 11))
                            .foregroundStyle(Ink.muted)
                        Text("Saves itself in \(countdown)s").gulpLabel()
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, Space.x3)
                }
            case .sending:
                HStack(spacing: Space.x3) {
                    ProgressView().tint(Ink.muted)
                    Text("Forwarding").gulpLabel()
                }
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .padding(.top, Space.x4)
            case .sent:
                confirmation("checkmark", "In your inbox")
            case .queued:
                // Not an error. The capture is kept; the app sends it later.
                confirmation("tray.and.arrow.down", "Saved — it'll send when you're back online")
            case let .failed(message):
                InlineError(message: message).padding(.top, Space.x4)
                PrimaryButton(title: "Try again") { send() }
                    .padding(.top, Space.x3)
            }
        }
        .padding(.horizontal, Space.x5)
        .padding(.top, Space.x5)
        .padding(.bottom, Space.x6)
        .frame(maxWidth: .infinity)
        .task {
            if draft.isEmpty { pasteFocused = true }
            startCountdown()
        }
        .onDisappear { timer?.cancel() }
    }

    private func confirmation(_ symbol: String, _ text: String) -> some View {
        HStack(spacing: Space.x2) {
            Image(systemName: symbol).font(.system(size: 13, weight: .semibold))
            Text(text).font(GulpFont.rowTitle)
        }
        .foregroundStyle(Ink.primary)
        .frame(maxWidth: .infinity)
        .frame(height: 48)
        .padding(.top, Space.x4)
    }

    // The true one-gesture path is share → done (`01 §F1`). Any touch on the
    // sheet cancels the countdown, because someone who started typing has said
    // they want a moment.
    private func startCountdown() {
        guard let seconds = autoConfirmAfter, canSend else { return }
        countdown = seconds
        timer = Task {
            while countdown > 0 {
                try? await Task.sleep(for: .seconds(1))
                if Task.isCancelled { return }
                countdown -= 1
            }
            if !Task.isCancelled { send() }
        }
    }

    private func stopCountdown() {
        timer?.cancel()
        countdown = 0
    }

    private func send() {
        stopCountdown()
        guard canSend, delivery != .sending, delivery != .sent else { return }
        let outgoing = composed
        delivery = .sending
        Task {
            switch await ForwardService.forward(outgoing) {
            case .sent:
                delivery = .sent
                try? await Task.sleep(for: .milliseconds(700))
                finish()
            case .queued:
                delivery = .queued
                try? await Task.sleep(for: .milliseconds(1200))
                finish()
            case let .refused(message):
                delivery = .failed(message)
            }
        }
    }
}
