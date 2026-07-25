import SwiftUI

// Design tokens — the *mobile* register of `docs/03 §3.2`, transcribed once.
// Never pick a colour, radius or spacing value at a call site.
//
// v1 is light-theme only (`03 §10` defers dark), so these are flat values
// rather than dynamic colours. When dark arrives it is a value swap here and
// nowhere else, which is the whole reason call sites don't hold literals.

extension Color {
    init(hex: UInt32) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: 1
        )
    }
}

enum Ink {
    /// App background — warm sand.
    static let paper = Color(hex: 0xFAFAF7)
    /// Cards and bars.
    static let surface = Color(hex: 0xFFFFFF)
    /// Subtle fill — search wells, formula blocks, glyph tiles.
    static let fill = Color(hex: 0xF4F3EE)
    /// Hairline.
    static let line = Color(hex: 0xE9E6DD)
    /// Stronger hairline — outlined controls, unfilled tick marks.
    static let lineStrong = Color(hex: 0xD8D3C7)
    /// Placeholder text.
    static let muted = Color(hex: 0xA8A395)
    /// Secondary text.
    static let secondary = Color(hex: 0x6B665A)
    /// Primary text — and the primary action (`spec §5.2`).
    static let primary = Color(hex: 0x1C1B18)
}

/// The five mastery states of `03 §3.3`. Shared spine: these values are
/// identical on web and must never be re-tinted per surface. A state may be
/// absent from a screen; it may not be recoloured.
enum Mastery {
    static let new = Color(hex: 0x94A3B8)
    static let learning = Color(hex: 0xF59E0B)
    static let known = Color(hex: 0x10B981)
    static let due = Color(hex: 0x2563EB)
    static let atRisk = Color(hex: 0xEF4444)
}

/// The only two accents this client uses.
///
/// `due` is the sole blue in the app: **blue means there is work here, and
/// nothing else** (`spec §2.4`). `streak` is the sole warm mark, and only at a
/// genuine moment of progress (`03 §1.2.4`).
enum Accent {
    static let due = Mastery.due
    static let streak = Color(hex: 0xF59E0B)
}

enum Radius {
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 20
}

/// 4 pt base (`03 §5.1`). Mobile reaches for 4/5/6 inside a component and
/// 8/10/12 between regions.
enum Space {
    static let x1: CGFloat = 4
    static let x2: CGFloat = 8
    static let x3: CGFloat = 12
    static let x4: CGFloat = 16
    static let x5: CGFloat = 20
    static let x6: CGFloat = 24
    static let x8: CGFloat = 32
    static let x10: CGFloat = 40
    static let x12: CGFloat = 48
}

enum Elevation {
    /// `--shadow-card`, the only elevation a resting surface gets.
    static func card<V: View>(_ view: V) -> some View {
        view.shadow(color: Color(hex: 0x1C1B18).opacity(0.08), radius: 4, x: 0, y: 2)
    }
}

extension View {
    /// A white card on paper: hairline, radius, and the one card shadow.
    func gulpCard(radius: CGFloat = Radius.lg) -> some View {
        self
            .background(Ink.surface)
            .clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .stroke(Ink.line, lineWidth: 1)
            )
            .shadow(color: Color(hex: 0x1C1B18).opacity(0.08), radius: 4, x: 0, y: 2)
    }
}
