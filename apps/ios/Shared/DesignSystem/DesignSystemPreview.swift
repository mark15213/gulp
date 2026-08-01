import SwiftUI

/// Every token, both families, all three tick styles, on one screen. This is
/// the app's first screen until Task 3 lands the real shell — if the design
/// system is wrong, it is wrong here first.
struct DesignSystemPreview: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Space.x8) {
                section("Type") {
                    Text("Attention Is All You Need").font(GulpFont.titleL)
                    Text("The daily home answers one question.").font(GulpFont.body)
                        .foregroundStyle(Ink.secondary)
                    Text("Wed · Jul 25").gulpLabel()
                    Text("12").gulpData(44)
                }

                section("Ticks") {
                    DueGauge(new: 4, reviews: 8)
                    SessionRail(total: 12, done: 5)
                    HStack {
                        Text("Attention Is All You Need").font(GulpFont.rowTitle)
                        Spacer()
                        TickMarks(filled: 3, style: .due, counting: "cards due")
                    }
                }

                section("Chips") {
                    HStack(spacing: Space.x2) {
                        StateChip(kind: .ready)
                        StateChip(kind: .processing)
                    }
                    HStack(spacing: Space.x2) {
                        StateChip(kind: .unprocessed)
                        StateChip(kind: .needsAttention)
                    }
                }

                section("Actions") {
                    PrimaryButton(title: "Start Gulp", systemImage: "arrow.right") {}
                    SecondaryButton(title: "Keep going") {}
                }

                section("Surfaces") {
                    VStack(alignment: .leading, spacing: Space.x3) {
                        Text("Key insight").gulpLabel()
                        Text("Once every position can look at every other position directly, the sequential bottleneck disappears.")
                            .font(GulpFont.bodyL)
                    }
                    .padding(Space.x4)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .gulpCard()
                }
            }
            .padding(Space.x5)
        }
        .background(Ink.paper)
    }

    private func section<C: View>(_ title: String, @ViewBuilder content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: Space.x4) {
            Text(title).gulpLabel()
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

#Preview {
    DesignSystemPreview()
}
