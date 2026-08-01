import SwiftUI
import GulpAPI

/// The hero flow (`03 §7.7`). No tab bar, no title bar, one thing per screen.
struct SessionView: View {
    @Environment(Auth.self) private var auth
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss

    @State private var model: SessionModel?

    var body: some View {
        ZStack {
            Ink.paper.ignoresSafeArea()
            if let model {
                content(model)
            } else {
                ProgressView().tint(Ink.muted)
            }
        }
        .task {
            guard model == nil else { return }
            let session = SessionModel(auth: auth)
            model = session
            await session.start(targetMinutes: app.sessionMinutes)
        }
    }

    @ViewBuilder
    private func content(_ model: SessionModel) -> some View {
        switch model.phase {
        case .building:
            VStack(spacing: Space.x4) {
                Text("Building your session").gulpLabel()
                ProgressView().tint(Ink.muted)
            }
        case .failed(let message):
            VStack(spacing: Space.x5) {
                InlineError(message: message)
                SecondaryButton(title: "Close") { close() }
            }
            .padding(.horizontal, Space.x5)
        case .complete:
            SummaryScreen(summary: model.summary, reviewed: model.total) { close() }
        case .prompt, .revealed:
            CardScreen(model: model, close: close)
        }
    }

    private func close() {
        app.sessionIsRunning = false
        Task { await app.refreshToday() }
        dismiss()
    }
}

// MARK: - One card

private struct CardScreen: View {
    @Bindable var model: SessionModel
    let close: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header

            if let card = model.card {
                Text(cardTypeLabel(card.card_type))
                    .gulpLabel()
                    .padding(.top, Space.x6)

                Text(card.prompt)
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundStyle(Ink.primary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, Space.x3)

                if model.phase == .revealed {
                    RevealBlock(card: card)
                        .padding(.top, Space.x4)
                }

                Spacer(minLength: Space.x5)

                // Everything actionable sits in the thumb zone (`03 §5.3`).
                if model.phase == .prompt {
                    answering(card)
                } else {
                    GradeRow(model: model)
                }
            }
        }
        .padding(.horizontal, Space.x5)
        .padding(.bottom, Space.x6)
    }

    private var header: some View {
        VStack(spacing: Space.x2) {
            HStack {
                Button(action: close) {
                    Image(systemName: "xmark")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundStyle(Ink.secondary)
                        .frame(width: 44, height: 44)
                        .offset(x: -Space.x3)
                }
                .accessibilityLabel("End session")
                Spacer()
                HStack(spacing: 4) {
                    Text("\(model.index + 1)").gulpData(11)
                    Text("/ \(model.total)").gulpLabel()
                }
            }
            // The same mark as Today's gauge: one segment, one card.
            SessionRail(total: model.total, done: model.index)
        }
    }

    @ViewBuilder
    private func answering(_ card: Components.Schemas.SessionCardOut) -> some View {
        if let options = card.options, !options.isEmpty {
            VStack(spacing: Space.x2) {
                ForEach(Array(options.enumerated()), id: \.offset) { offset, option in
                    OptionRow(letter: letter(offset), text: option) {
                        model.selection = option
                        model.reveal()
                    }
                }
            }
        } else {
            VStack(spacing: Space.x3) {
                GulpField(
                    placeholder: card.card_type == .cloze ? "Fill the blank" : "Say it in your own words",
                    text: $model.typed,
                    submitLabel: .done,
                    onSubmit: { model.reveal() }
                )
                PrimaryButton(title: "Show answer") { model.reveal() }
            }
        }
    }

    private func letter(_ offset: Int) -> String {
        String(UnicodeScalar(UInt8(65 + min(offset, 25))))
    }

    private func cardTypeLabel(_ type: Components.Schemas.SessionCardOut.card_typePayload) -> String {
        switch type {
        case .flashcard: "Flashcard"
        case .mcq: "Multiple choice"
        case .cloze: "Cloze"
        }
    }
}

private struct OptionRow: View {
    let letter: String
    let text: String
    let tap: () -> Void

    var body: some View {
        Button(action: tap) {
            HStack(spacing: Space.x3) {
                Text(letter)
                    .font(GulpFont.labelSmall)
                    .foregroundStyle(Ink.secondary)
                    .frame(width: 22, height: 22)
                    .background(Ink.fill)
                    .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                Text(text)
                    .font(GulpFont.bodyS)
                    .foregroundStyle(Ink.primary)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }
            .padding(Space.x3)
            .frame(minHeight: 52)
            .frame(maxWidth: .infinity, alignment: .leading)
            .gulpCard(radius: Radius.md)
        }
        .buttonStyle(.plain)
    }
}

/// Answer plus the source it came from — every answer is grounded, never
/// asserted (spec §2.2).
private struct RevealBlock: View {
    let card: Components.Schemas.SessionCardOut

    var body: some View {
        VStack(alignment: .leading, spacing: Space.x3) {
            if let answer = card.answer {
                Text("Answer").gulpLabel()
                Text(answer)
                    .font(GulpFont.bodyL)
                    .foregroundStyle(Ink.primary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let explanation = card.explanation {
                Text(explanation)
                    .font(GulpFont.bodyS)
                    .foregroundStyle(Ink.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let source = card.source_title {
                HStack(spacing: Space.x2) {
                    Image(systemName: "arrow.up.forward.square")
                        .font(.system(size: 12))
                        .foregroundStyle(Ink.muted)
                    Text(source).gulpLabel()
                }
                .padding(.top, Space.x1)
            }
        }
        .padding(Space.x4)
        .frame(maxWidth: .infinity, alignment: .leading)
        .gulpCard()
    }
}

/// Three grades, each a hairline pill with one mastery dot — the spine's
/// colour language survives without three coloured slabs on screen.
private struct GradeRow: View {
    let model: SessionModel

    var body: some View {
        HStack(spacing: Space.x2) {
            ForEach(SessionModel.Grade.allCases, id: \.self) { grade in
                Button {
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    Task { await model.grade(grade) }
                } label: {
                    VStack(spacing: Space.x2) {
                        HStack(spacing: Space.x2) {
                            Circle().fill(dot(grade)).frame(width: 6, height: 6)
                            Text(grade.label)
                                .font(GulpFont.rowTitle)
                                .foregroundStyle(Ink.primary)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 56)
                    .background(Ink.surface)
                    .clipShape(RoundedRectangle(cornerRadius: Radius.md, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: Radius.md, style: .continuous)
                            .stroke(Ink.lineStrong, lineWidth: 1)
                    )
                }
                .buttonStyle(.plain)
                .accessibilityLabel(grade.label)
            }
        }
    }

    private func dot(_ grade: SessionModel.Grade) -> Color {
        switch grade {
        case .missed: Mastery.atRisk
        case .fuzzy: Mastery.learning
        case .gotIt: Mastery.known
        }
    }
}

// MARK: - Summary

private struct SummaryScreen: View {
    let summary: Components.Schemas.SummaryOut?
    let reviewed: Int
    let done: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Session complete").gulpLabel()
                Spacer()
                if let streak = summary?.streak_days, streak > 0 {
                    HStack(spacing: Space.x1) {
                        Image(systemName: "flame.fill")
                            .font(.system(size: 11))
                            .foregroundStyle(Accent.streak)
                        Text("\(streak)").gulpData(11)
                        Text("days").gulpLabel()
                    }
                }
            }
            .padding(.top, Space.x6)

            // The rail closes the loop it opened on Today.
            SessionRail(total: max(reviewed, 1), done: max(reviewed, 1))
                .padding(.top, Space.x3)

            HStack(alignment: .lastTextBaseline, spacing: Space.x3) {
                Text("\(summary?.reviewed_count ?? reviewed)")
                    .font(GulpFont.data(44))
                    .monospacedDigit()
                Text("cards").font(GulpFont.bodyL).foregroundStyle(Ink.secondary)
            }
            .padding(.top, Space.x8)

            VStack(spacing: 0) {
                row("Newly known", summary?.newly_mastered ?? 0)
                Rectangle().fill(Ink.line).frame(height: 1)
                row("Still fuzzy", summary?.still_fuzzy ?? 0)
                Rectangle().fill(Ink.line).frame(height: 1)
                row("Waiting in your inbox", summary?.next_up.inbox_count ?? 0)
            }
            .padding(.top, Space.x5)

            Spacer()

            PrimaryButton(title: "Done", action: done)
        }
        .padding(.horizontal, Space.x5)
        .padding(.bottom, Space.x6)
    }

    private func row(_ label: String, _ value: Int) -> some View {
        HStack {
            Text(label).font(GulpFont.body).foregroundStyle(Ink.primary)
            Spacer()
            Text("\(value)").gulpData(19)
        }
        .padding(.vertical, Space.x4)
    }
}
