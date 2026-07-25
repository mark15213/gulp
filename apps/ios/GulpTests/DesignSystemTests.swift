import Testing
import SwiftUI
@testable import Gulp

// The design system is mostly declarative, so these guard the parts that can
// silently drift: the shared spine values, and the arithmetic behind the one
// device that appears on three screens.

@Suite("Mastery palette is shared spine")
struct MasteryPaletteTests {
    /// `03 §1.1` fixes these as non-diverging. If someone "adjusts" one for
    /// mobile, this fails — which is the point.
    @Test func spineValuesAreUnchanged() {
        #expect(Mastery.new.hexString == "94A3B8")
        #expect(Mastery.learning.hexString == "F59E0B")
        #expect(Mastery.known.hexString == "10B981")
        #expect(Mastery.due.hexString == "2563EB")
        #expect(Mastery.atRisk.hexString == "EF4444")
    }

    /// Blue means exactly one thing in this client (`spec §2.4`).
    @Test func blueIsOnlyDue() {
        #expect(Accent.due.hexString == Mastery.due.hexString)
        #expect(Ink.primary.hexString != Mastery.due.hexString)
    }
}

@Suite("Tick marks")
struct TickMarkTests {
    @Test func railCoversEveryCardExactlyOnce() {
        let rail = SessionRail(total: 12, done: 5)
        #expect(rail.total == 12)
        #expect(rail.done == 5)
    }

    @Test func negativeCountsCannotDrawMarks() {
        let ticks = TickMarks(filled: -3, empty: -1, counting: "cards")
        #expect(ticks.filled == 0)
        #expect(ticks.empty == 0)
    }

    /// An item with nothing due draws nothing — the empty right edge in
    /// Library is information, not an omission.
    @Test func restingRowDrawsNoMarks() {
        let ticks = TickMarks(filled: 0, style: .due, counting: "cards due")
        #expect(ticks.filled == 0)
        #expect(ticks.empty == 0)
    }
}

@Suite("State chips")
struct StateChipTests {
    /// `03 §9`: state is never colour-only, so every kind must have a label.
    @Test func everyKindIsLabelled() {
        let kinds: [StateChip.Kind] = [.ready, .processing, .unprocessed, .needsAttention, .correct]
        for kind in kinds {
            #expect(!kind.label.isEmpty)
        }
    }

    @Test func onlyProcessingAnimates() {
        #expect(StateChip.Kind.processing.pulses)
        #expect(!StateChip.Kind.ready.pulses)
        #expect(!StateChip.Kind.unprocessed.pulses)
    }
}

// MARK: - Helpers

extension Color {
    /// sRGB hex, for comparing token values in tests.
    var hexString: String {
        let components = UIColor(self).cgColor.components ?? []
        guard components.count >= 3 else { return "" }
        let r = Int((components[0] * 255).rounded())
        let g = Int((components[1] * 255).rounded())
        let b = Int((components[2] * 255).rounded())
        return String(format: "%02X%02X%02X", r, g, b)
    }
}
