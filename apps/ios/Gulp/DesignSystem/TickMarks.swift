import SwiftUI

// The signature device (`spec §2.1`). **One tick, one card.**
//
// It appears three times and means the same thing every time, which is the
// whole point — do not re-draw it per screen:
//
//   .gauge     Today's hero, split into new / review groups
//   .rail      the session progress bar
//   .due       Library's right-hand column, in the one blue this app has
//
// Because a mark is a quantity and not a state, it never carries a label of
// its own; the surrounding text names what is being counted, and VoiceOver
// gets a count rather than a run of marks.

struct TickMarks: View {
    enum Style {
        /// Vertical strokes beside the hero numeral.
        case gauge
        /// Thin horizontal segments across the top of a session screen.
        case rail
        /// Compact strokes at the trailing edge of a list row.
        case due
    }

    /// Marks drawn in ink (or blue, for `.due`).
    let filled: Int
    /// Marks drawn in the strong hairline — present but not yet yours.
    let empty: Int
    let style: Style
    /// What the marks count, for VoiceOver: "3 cards due".
    let accessibilityCounting: String

    init(
        filled: Int,
        empty: Int = 0,
        style: Style = .gauge,
        counting accessibilityCounting: String
    ) {
        self.filled = max(0, filled)
        self.empty = max(0, empty)
        self.style = style
        self.accessibilityCounting = accessibilityCounting
    }

    private var filledColor: Color {
        style == .due ? Accent.due : Ink.primary
    }

    private var emptyColor: Color {
        style == .rail ? Ink.lineStrong : Ink.lineStrong
    }

    private var width: CGFloat { style == .rail ? 0 : 3 }
    private var height: CGFloat {
        switch style {
        case .gauge: 22
        case .rail: 3
        case .due: 20
        }
    }

    private var gap: CGFloat {
        switch style {
        case .gauge: 7
        case .rail: 5
        case .due: 4
        }
    }

    var body: some View {
        HStack(spacing: gap) {
            ForEach(0 ..< filled, id: \.self) { _ in mark(filledColor) }
            ForEach(0 ..< empty, id: \.self) { _ in mark(emptyColor) }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(filled) \(accessibilityCounting)")
    }

    @ViewBuilder
    private func mark(_ color: Color) -> some View {
        if style == .rail {
            Capsule().fill(color).frame(height: height)
        } else {
            Capsule().fill(color).frame(width: width, height: height)
        }
    }
}

/// Today's hero gauge.
///
/// Tone follows the same rule as the rail: **hairline means you haven't met
/// this one yet, ink means you have.** New cards are hairline because you have
/// never seen them; reviews are ink because you have. Keeping one meaning for
/// fill across all three uses is what stops the mark from becoming decoration.
struct DueGauge: View {
    let new: Int
    let reviews: Int

    var body: some View {
        HStack(alignment: .bottom, spacing: Space.x4) {
            group(count: new, label: "New", met: false)
            group(count: reviews, label: "Reviews", met: true)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(new) new, \(reviews) reviews")
    }

    private func group(count: Int, label: String, met: Bool) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            TickMarks(
                filled: met ? count : 0,
                empty: met ? 0 : count,
                style: .gauge,
                counting: label.lowercased()
            )
            .accessibilityHidden(true)
            HStack(spacing: 4) {
                Text("\(count)").gulpData(11)
                Text(label).gulpLabel()
            }
        }
    }
}

/// The session rail — one segment per card, filled as you go.
struct SessionRail: View {
    let total: Int
    let done: Int

    var body: some View {
        TickMarks(
            filled: min(done, total),
            empty: max(0, total - done),
            style: .rail,
            counting: "of \(total) cards done"
        )
    }
}
