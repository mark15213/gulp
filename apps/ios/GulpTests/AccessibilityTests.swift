import Testing
import SwiftUI
@testable import Gulp

/// Task 10's checks that can be made without a human looking at a screen.
/// The rest — Dynamic Type at XXXL on every screen, VoiceOver order — needs
/// eyes and a device, and is listed in the plan rather than claimed here.
@Suite("Accessibility invariants")
struct AccessibilityTests {
    /// `03 §3.6`: body text ≥ 7:1, interactive ≥ 4.5:1. The palette is fixed,
    /// so this is checkable arithmetic rather than an opinion.
    @Test func inkOnPaperClearsTheBodyBudget() {
        #expect(contrast(Ink.primary, Ink.paper) >= 7.0)
    }

    @Test func primaryActionClearsTheInteractiveBudget() {
        // White on the ink button.
        #expect(contrast(Ink.surface, Ink.primary) >= 4.5)
    }

    @Test func secondaryTextIsStillReadable() {
        #expect(contrast(Ink.secondary, Ink.paper) >= 4.5)
    }

    /// Blue only ever appears as a small mark, but it still has to be legible
    /// against the paper it sits on.
    @Test func dueBlueIsLegibleOnPaper() {
        #expect(contrast(Accent.due, Ink.paper) >= 4.5)
    }

    private func contrast(_ a: Color, _ b: Color) -> Double {
        let la = luminance(a), lb = luminance(b)
        let (hi, lo) = la > lb ? (la, lb) : (lb, la)
        return (hi + 0.05) / (lo + 0.05)
    }

    private func luminance(_ color: Color) -> Double {
        let components = UIColor(color).cgColor.components ?? [0, 0, 0]
        func channel(_ value: CGFloat) -> Double {
            let v = Double(value)
            return v <= 0.03928 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4)
        }
        guard components.count >= 3 else { return 0 }
        return 0.2126 * channel(components[0])
            + 0.7152 * channel(components[1])
            + 0.0722 * channel(components[2])
    }
}
