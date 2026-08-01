import SwiftUI

/// Task 7. Account, the mastery bar Today evicted, streak figures, session
/// length, and the line naming what the phone deliberately doesn't do.
/// Sign-out is here already because the shell needs a way back out.
struct YouView: View {
    @Environment(Auth.self) private var auth

    var body: some View {
        VStack(alignment: .leading, spacing: Space.x4) {
            Text("You").font(GulpFont.screenTitle)

            if let user = auth.user {
                VStack(alignment: .leading, spacing: Space.x2) {
                    Text("Signed in").gulpLabel()
                    Text(user.email).gulpData(14)
                }
                .padding(Space.x4)
                .frame(maxWidth: .infinity, alignment: .leading)
                .gulpCard()
            }

            Text("Task 7 lands here.")
                .font(GulpFont.body)
                .foregroundStyle(Ink.secondary)

            Spacer()

            SecondaryButton(title: "Sign out") {
                Task { await auth.signOut() }
            }
            .padding(.bottom, Space.x4)
        }
        .padding(.horizontal, Space.x5)
        .padding(.top, Space.x4)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Ink.paper)
    }
}
