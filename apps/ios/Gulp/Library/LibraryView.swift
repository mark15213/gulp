import SwiftUI

/// Task 6. The shelf: search first, filters as a mono row, and a trailing
/// column of `Due` ticks (spec §2.4).
struct LibraryView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Space.x4) {
            Text("Library").font(GulpFont.screenTitle)
            Text("Task 6 lands here.")
                .font(GulpFont.body)
                .foregroundStyle(Ink.secondary)
            Spacer()
        }
        .padding(.horizontal, Space.x5)
        .padding(.top, Space.x4)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Ink.paper)
    }
}
