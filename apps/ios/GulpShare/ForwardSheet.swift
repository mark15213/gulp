import SwiftUI
import GulpAPI

/// The sheet. The verb is **Forward**, never Gulp — forwarding is how things
/// get in, gulping is what you do with them later (spec §2.3).
struct ForwardSheet: View {
    let payload: SharePayload
    let finish: () -> Void

    @State private var note = ""
    @State private var tags = ""
    @State private var countdown = 3
    @State private var delivery: Delivery = .waiting
    @State private var autoConfirm: Task<Void, Never>?

    /// Deliberately not named `State`: the nested type would shadow
    /// SwiftUI's `@State`, the same way `Tab` shadows the tab builder.
    private enum Delivery: Equatable {
        case waiting, sending, sent, failed(String)
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            Color.black.opacity(0.42)
                .ignoresSafeArea()
                .onTapGesture { cancel() }

            VStack(alignment: .leading, spacing: 0) {
                Capsule().fill(Ink.lineStrong).frame(width: 36, height: 4)
                    .frame(maxWidth: .infinity)
                    .padding(.bottom, Space.x4)

                Text("Forward to Gulp").gulpLabel()

                Text(payload.detectedTitle)
                    .font(GulpFont.titleS)
                    .foregroundStyle(Ink.primary)
                    .lineLimit(2)
                    .padding(.top, Space.x3)

                if let host = payload.host {
                    Text(host).gulpLabel().padding(.top, Space.x2)
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
                    HStack(spacing: Space.x2) {
                        Image(systemName: "checkmark").font(.system(size: 13, weight: .semibold))
                        Text("In your inbox").font(GulpFont.rowTitle)
                    }
                    .foregroundStyle(Ink.primary)
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .padding(.top, Space.x4)
                case let .failed(message):
                    InlineError(message: message).padding(.top, Space.x4)
                    PrimaryButton(title: "Try again") { send() }
                        .padding(.top, Space.x3)
                }
            }
            .padding(.horizontal, Space.x5)
            .padding(.top, Space.x3)
            .padding(.bottom, Space.x6)
            .frame(maxWidth: .infinity)
            .background(Ink.surface)
            .clipShape(
                UnevenRoundedRectangle(
                    topLeadingRadius: Radius.xl,
                    topTrailingRadius: Radius.xl,
                    style: .continuous
                )
            )
        }
        // The true one-gesture path is share → done (`01 §F1`). Any touch on
        // the sheet cancels the countdown, because a person who started typing
        // has said they want a moment.
        .task { startCountdown() }
    }

    private func startCountdown() {
        autoConfirm = Task {
            while countdown > 0 {
                try? await Task.sleep(for: .seconds(1))
                if Task.isCancelled { return }
                countdown -= 1
            }
            if !Task.isCancelled { send() }
        }
    }

    private func stopCountdown() {
        autoConfirm?.cancel()
        countdown = 0
    }

    private func cancel() {
        stopCountdown()
        finish()
    }

    private func send() {
        stopCountdown()
        guard delivery != .sending, delivery != .sent else { return }
        delivery = .sending
        Task {
            do {
                let client = GulpClientFactory.make()
                let parsed = tags
                    .split(separator: ",")
                    .map { $0.trimmingCharacters(in: .whitespaces) }
                    .filter { !$0.isEmpty }
                let output = try await client.capture_capture_post(
                    body: .json(.init(
                        url: payload.url,
                        text: payload.url == nil ? payload.text : nil,
                        note: note.isEmpty ? nil : note,
                        title: payload.url == nil ? nil : payload.detectedTitle,
                        tags: parsed.isEmpty ? nil : parsed
                    ))
                )
                switch output {
                case .ok:
                    delivery = .sent
                    try? await Task.sleep(for: .milliseconds(700))
                    finish()
                case let .undocumented(statusCode, _):
                    delivery = .failed(statusCode == 401
                        ? "Sign in to Gulp on your phone first."
                        : "Couldn't forward that (\(statusCode)).")
                default:
                    delivery = .failed("Couldn't forward that.")
                }
            } catch {
                delivery = .failed(error.asGulpError.display)
            }
        }
    }
}
