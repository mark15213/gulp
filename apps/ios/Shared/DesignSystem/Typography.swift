import SwiftUI

// Two families, fixed roles (`03 §2.3`, as amended 2026-07-25 — the serif is
// cut). Inter carries words; Geist Mono carries every number, count, interval
// and uppercase label. There is no third family.
//
// Sizes are the *mobile* column of `03 §4.2`. Components reference the named
// roles below, never a raw size.

enum GulpFont {
    /// Geist Mono ships in `design/fonts/` and is bundled. Inter is not
    /// vendored in the repo yet, so the sans role falls back to the system
    /// face — visually close (both neo-grotesque) but not the spec'd family.
    /// Vendoring Inter is a one-file change: drop the variable font into
    /// `Resources/Fonts/` and set `sansName`.
    private static let monoName = "GeistMono-Regular"
    private static let sansName: String? = nil

    private static func sans(_ size: CGFloat, _ weight: Font.Weight) -> Font {
        if let sansName {
            return .custom(sansName, size: size).weight(weight)
        }
        return .system(size: size, weight: weight)
    }

    private static func mono(_ size: CGFloat) -> Font {
        .custom(monoName, size: size)
    }

    // MARK: - Roles

    static let titleL = sans(28, .semibold)
    static let titleM = sans(20, .semibold)
    static let titleS = sans(17, .semibold)

    /// Screen title on a list surface (`Library`, `You`).
    static let screenTitle = sans(26, .semibold)

    static let bodyL = sans(17, .regular)
    /// Default body.
    static let body = sans(16, .regular)
    static let bodyS = sans(14, .regular)
    static let caption = sans(13, .regular)

    /// Row titles in a list — the one place body text carries weight.
    static let rowTitle = sans(15, .medium)

    /// Uppercase overline / section label. Always paired with
    /// `.tracking(0.08 * size)` via `.gulpLabel()`.
    static let label = mono(11)
    static let labelSmall = mono(10)

    /// Numerals — always tabular so figures don't jitter as they update.
    static func data(_ size: CGFloat) -> Font { mono(size) }

    /// The hero numeral on Today. Carries the moment a display serif used to.
    static let hero = mono(68)
}

extension Text {
    /// Mono overline: uppercase, tracked, muted by default.
    func gulpLabel(_ color: Color = Ink.muted) -> some View {
        self
            .font(GulpFont.label)
            .tracking(0.88) // 0.08em at 11pt
            .textCase(.uppercase)
            .foregroundStyle(color)
            .monospacedDigit()
    }

    /// Any count, interval, streak or timestamp.
    func gulpData(_ size: CGFloat = 13, color: Color = Ink.primary) -> some View {
        self
            .font(GulpFont.data(size))
            .foregroundStyle(color)
            .monospacedDigit()
    }
}
