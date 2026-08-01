import SwiftUI

// `03 §7.2`, as amended 2026-07-25: on iOS the chip is a hairline pill with a
// coloured dot, not a tinted fill. Colour plus label still carries the state,
// so §9 holds — the label is never optional.

struct StateChip: View {
    enum Kind {
        case ready
        case processing
        case unprocessed
        case needsAttention
        case correct

        var label: String {
            switch self {
            case .ready: "Ready"
            case .processing: "Processing"
            case .unprocessed: "Not started"
            case .needsAttention: "Needs attention"
            case .correct: "Correct"
            }
        }

        var dot: Color {
            switch self {
            case .ready, .correct: Mastery.known
            case .processing, .unprocessed: Ink.muted
            case .needsAttention: Mastery.atRisk
            }
        }

        /// Only `processing` breathes, and only when motion is allowed.
        var pulses: Bool { self == .processing }
    }

    let kind: Kind
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var dim = false

    var body: some View {
        HStack(spacing: 5) {
            Circle()
                .fill(kind.dot)
                .frame(width: 5, height: 5)
                .opacity(dim ? 0.25 : 1)
            Text(kind.label)
                .font(GulpFont.labelSmall)
                .tracking(0.8)
                .textCase(.uppercase)
                .foregroundStyle(Ink.secondary)
        }
        .padding(.horizontal, Space.x2)
        .frame(height: 20)
        .overlay(Capsule().stroke(Ink.lineStrong, lineWidth: 1))
        .onAppear {
            guard kind.pulses, !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) {
                dim = true
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(kind.label)
    }
}

/// The one primary action on a screen. Ink, never blue (`spec §5.2`).
struct PrimaryButton: View {
    let title: String
    var systemImage: String?
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Space.x2) {
                Text(title).font(GulpFont.titleS)
                if let systemImage {
                    Image(systemName: systemImage).font(.system(size: 14, weight: .semibold))
                }
            }
            .frame(maxWidth: .infinity)
            .frame(height: 48)
            .foregroundStyle(Ink.surface)
            .background(Ink.primary)
            .clipShape(RoundedRectangle(cornerRadius: Radius.md, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

/// Alternatives and low-emphasis actions — hairline, never filled.
struct SecondaryButton: View {
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(GulpFont.rowTitle)
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .foregroundStyle(Ink.secondary)
                .overlay(
                    RoundedRectangle(cornerRadius: Radius.md, style: .continuous)
                        .stroke(Ink.lineStrong, lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
    }
}
