import SwiftUI

/// Decides which of the three worlds the app is in. Screens never ask "am I
/// signed in?" — they are only ever built inside the signed-in branch.
struct RootView: View {
    @Environment(Auth.self) private var auth
    @State private var didRestore = false

    var body: some View {
        Group {
            switch auth.state {
            case .unknown:
                // Not "signed out" — we haven't asked yet, or we asked and the
                // network refused to answer. Bouncing a signed-in user to a
                // login form because of a dropped connection is worse than
                // waiting.
                RestoringView(retry: restore)
            case .signedOut:
                SignInView()
            case .signedIn:
                MainTabs()
            }
        }
        .task {
            guard !didRestore else { return }
            didRestore = true
            await auth.restore()
        }
    }

    private func restore() {
        Task { await auth.restore() }
    }
}

private struct RestoringView: View {
    let retry: () -> Void
    @State private var showRetry = false

    var body: some View {
        VStack(spacing: Space.x4) {
            Text("Gulp").gulpLabel(Ink.secondary)
            if showRetry {
                Text("Can't reach Gulp right now.")
                    .font(GulpFont.body)
                    .foregroundStyle(Ink.secondary)
                Button("Try again", action: retry)
                    .font(GulpFont.rowTitle)
                    .foregroundStyle(Ink.primary)
                    .frame(height: 44)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Ink.paper)
        .task {
            // Give the restore a moment before admitting defeat, so a fast
            // launch never flashes an error.
            try? await Task.sleep(for: .seconds(2))
            showRetry = true
        }
    }
}
