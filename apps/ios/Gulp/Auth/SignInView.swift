import SwiftUI

/// The only screen a signed-out user sees. Two fields and one action; the
/// register path is the same form with a different verb, because it is the
/// same two facts either way.
struct SignInView: View {
    @Environment(Auth.self) private var auth

    @State private var mode: Mode = .signIn
    @State private var email = ""
    @State private var password = ""
    @State private var error: String?

    private enum Mode {
        case signIn, register

        var action: String { self == .signIn ? "Sign in" : "Create account" }
        var switchPrompt: String {
            self == .signIn ? "Create an account" : "I already have an account"
        }
        var line: String {
            self == .signIn
                ? "Everything you've forwarded is waiting."
                : "Forward anything. Gulp turns it into knowledge you can actually remember."
        }
    }

    private var canSubmit: Bool {
        !email.isEmpty && password.count >= 8 && !auth.isWorking
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: Space.x12)

            Text("Gulp").gulpLabel(Ink.secondary)
            Text(mode.line)
                .font(GulpFont.titleM)
                .foregroundStyle(Ink.primary)
                .padding(.top, Space.x3)
                .fixedSize(horizontal: false, vertical: true)

            VStack(spacing: Space.x3) {
                GulpField(
                    placeholder: "Email",
                    text: $email,
                    contentType: .username,
                    keyboard: .emailAddress
                )
                GulpField(
                    placeholder: "Password",
                    text: $password,
                    isSecure: true,
                    contentType: mode == .signIn ? .password : .newPassword,
                    submitLabel: .go,
                    onSubmit: submit
                )
            }
            .padding(.top, Space.x8)

            if let error {
                InlineError(message: error).padding(.top, Space.x3)
            }

            PrimaryButton(title: mode.action) { submit() }
                .padding(.top, Space.x5)
                .opacity(canSubmit ? 1 : 0.4)
                .disabled(!canSubmit)

            Button {
                withAnimation(.easeOut(duration: 0.15)) {
                    mode = mode == .signIn ? .register : .signIn
                    error = nil
                }
            } label: {
                Text(mode.switchPrompt)
                    .font(GulpFont.bodyS)
                    .foregroundStyle(Ink.secondary)
                    .frame(maxWidth: .infinity)
                    .frame(height: 44)
            }
            .buttonStyle(.plain)
            .padding(.top, Space.x2)

            Spacer()

            Text("New accounts need a password of at least 8 characters.")
                .font(GulpFont.caption)
                .foregroundStyle(Ink.muted)
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.bottom, Space.x4)
        }
        .padding(.horizontal, Space.x5)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Ink.paper)
    }

    private func submit() {
        guard canSubmit else { return }
        error = nil
        Task {
            do {
                switch mode {
                case .signIn:
                    try await auth.signIn(email: email, password: password)
                case .register:
                    try await auth.register(email: email, password: password)
                }
            } catch {
                self.error = error.asGulpError.display
            }
        }
    }
}
