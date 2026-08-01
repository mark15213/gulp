import SwiftUI

/// Text input, `03 §7.13` in the mobile register: hairline, radius `md`,
/// 48 pt tall so it clears the touch minimum with room to spare.
struct GulpField: View {
    let placeholder: String
    @Binding var text: String
    var isSecure = false
    var contentType: UITextContentType?
    var keyboard: UIKeyboardType = .default
    var submitLabel: SubmitLabel = .next
    var onSubmit: () -> Void = {}

    @FocusState private var focused: Bool

    var body: some View {
        Group {
            if isSecure {
                SecureField(placeholder, text: $text)
            } else {
                TextField(placeholder, text: $text)
            }
        }
        .font(GulpFont.body)
        .foregroundStyle(Ink.primary)
        .tint(Ink.primary)
        .textInputAutocapitalization(.never)
        .autocorrectionDisabled()
        .textContentType(contentType)
        .keyboardType(keyboard)
        .submitLabel(submitLabel)
        .onSubmit(onSubmit)
        .focused($focused)
        .padding(.horizontal, Space.x3)
        .frame(height: 48)
        .background(Ink.surface)
        .clipShape(RoundedRectangle(cornerRadius: Radius.md, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Radius.md, style: .continuous)
                .stroke(focused ? Ink.primary : Ink.line, lineWidth: 1)
        )
        .animation(.easeOut(duration: 0.12), value: focused)
    }
}

/// Failure text. `03 §2.7`: say what happened and what to do, never blame.
struct InlineError: View {
    let message: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: Space.x2) {
            Circle()
                .fill(Mastery.atRisk)
                .frame(width: 5, height: 5)
                .offset(y: -2)
            Text(message)
                .font(GulpFont.bodyS)
                .foregroundStyle(Ink.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}
