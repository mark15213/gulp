import SwiftUI

/// The extension's host for `ForwardForm`: a dimmed backdrop and a bottom
/// sheet, because an extension draws its own modal rather than being presented
/// as one. The form itself is shared with the app's `+` — there is one
/// definition of what forwarding looks like.
struct ForwardSheet: View {
    let draft: ForwardDraft
    let finish: () -> Void

    var body: some View {
        ZStack(alignment: .bottom) {
            Color.black.opacity(0.42)
                .ignoresSafeArea()
                .onTapGesture { finish() }

            VStack(spacing: 0) {
                Capsule().fill(Ink.lineStrong).frame(width: 36, height: 4)
                    .padding(.top, Space.x3)
                ForwardForm(draft: draft, autoConfirmAfter: 3, finish: finish)
            }
            .background(Ink.surface)
            .clipShape(
                UnevenRoundedRectangle(
                    topLeadingRadius: Radius.xl,
                    topTrailingRadius: Radius.xl,
                    style: .continuous
                )
            )
        }
    }
}
