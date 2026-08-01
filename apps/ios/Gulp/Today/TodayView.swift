import SwiftUI
import GulpAPI

/// The daily home. Answers "what now" and nothing else (spec §2.1).
struct TodayView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                Text(Date.now, format: .dateTime.weekday(.abbreviated).month(.abbreviated).day())
                    .gulpLabel(Ink.secondary)
                    .padding(.top, Space.x2)

                switch model.todayLoad {
                case .idle, .loading:
                    TodaySkeleton().padding(.top, Space.x3)
                case let .failed(message):
                    InlineError(message: message).padding(.top, Space.x6)
                    SecondaryButton(title: "Try again") {
                        Task { await model.refreshToday() }
                    }
                    .padding(.top, Space.x4)
                case .loaded:
                    loaded
                }
            }
            .padding(.horizontal, Space.x5)
            .padding(.bottom, Space.x10)
        }
        .background(Ink.paper)
        .refreshable { await model.refreshToday() }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                // Capture lives here, not in a tab: the share sheet is the
                // real entry (spec §0). Task 9 gives it the same sheet.
                Button { } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 17, weight: .medium))
                        .foregroundStyle(Ink.primary)
                        .frame(width: 44, height: 44)
                }
                .accessibilityLabel("Forward something")
            }
        }
    }

    @ViewBuilder
    private var loaded: some View {
        let today = model.today
        let due = today?.due_count ?? 0
        let new = today?.new_count ?? 0

        if due == 0 {
            NothingDue(readyCount: today?.ready_count ?? 0)
                .padding(.top, Space.x6)
        } else {
            HeroCard(due: due, new: new, reviews: max(0, due - new)) {
                model.sessionIsRunning = true
            }
            .padding(.top, Space.x3)
        }

        if let recent = today?.recent, !recent.isEmpty {
            RecentlyForwarded(snapshots: recent)
                .padding(.top, Space.x8)
        } else {
            EmptyPeek().padding(.top, Space.x8)
        }
    }
}

// MARK: - Hero

private struct HeroCard: View {
    let due: Int
    let new: Int
    let reviews: Int
    let start: () -> Void

    /// Five minutes is the default session, and the cards-per-minute figure
    /// only has to be honest enough to set an expectation.
    private var minutes: Int { max(1, Int((Double(due) / 2.4).rounded())) }

    private var numeral: some View {
        Text("\(due)")
            .font(GulpFont.hero)
            .monospacedDigit()
            .foregroundStyle(Ink.primary)
            .fixedSize()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Due today").gulpLabel()
                Spacer()
                HStack(spacing: 4) {
                    Text("≈").gulpLabel()
                    Text("\(minutes)").gulpData(11)
                    Text("min").gulpLabel()
                }
            }

            // Side by side on a light day, stacked on a heavy one. The
            // mockups assumed twelve cards; twenty does not fit beside a
            // 68 pt numeral, and wrapping the labels looked broken.
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .bottom, spacing: Space.x6) {
                    numeral
                    DueGauge(new: new, reviews: reviews).padding(.bottom, Space.x1)
                }
                VStack(alignment: .leading, spacing: Space.x4) {
                    numeral
                    DueGauge(new: new, reviews: reviews)
                }
            }
            .padding(.top, Space.x4)

            PrimaryButton(title: "Start Gulp", systemImage: "arrow.right", action: start)
                .padding(.top, Space.x5)
        }
        .padding(Space.x5)
        .gulpCard(radius: Radius.xl)
    }
}

/// Never a dead end (`01 §F4`): if nothing is due, say what is here instead.
private struct NothingDue: View {
    let readyCount: Int

    var body: some View {
        VStack(alignment: .leading, spacing: Space.x3) {
            Text("Nothing due").gulpLabel()
            Text(readyCount == 0
                 ? "Forward something and it'll be waiting here."
                 : "You're clear for today. Come back tomorrow, or read something you've kept.")
                .font(GulpFont.bodyL)
                .foregroundStyle(Ink.primary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Space.x5)
        .frame(maxWidth: .infinity, alignment: .leading)
        .gulpCard(radius: Radius.xl)
    }
}

// MARK: - Recently forwarded

/// The compensation for having no Inbox tab on the phone (`01 §4.3`):
/// capture must never look like a black hole.
private struct RecentlyForwarded: View {
    @Environment(AppModel.self) private var model
    let snapshots: [Components.Schemas.SnapshotOut]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Recently forwarded").gulpLabel()
                Spacer()
            }

            ForEach(Array(snapshots.prefix(4).enumerated()), id: \.element.id) { index, snapshot in
                if index > 0 {
                    Rectangle().fill(Ink.line).frame(height: 1)
                }
                if snapshot.status == .ready {
                    NavigationLink { ReaderView(snapshot: snapshot) } label: {
                        SnapshotRow(snapshot: snapshot) {}
                    }
                    .buttonStyle(.plain)
                } else {
                    SnapshotRow(snapshot: snapshot) {
                        Task { await model.startProcessing(snapshot.id) }
                    }
                }
            }
            .padding(.top, Space.x2)
        }
    }
}

private struct SnapshotRow: View {
    let snapshot: Components.Schemas.SnapshotOut
    let start: () -> Void

    var body: some View {
        HStack(spacing: Space.x3) {
            VStack(alignment: .leading, spacing: Space.x2) {
                Text(snapshot.title)
                    .font(GulpFont.rowTitle)
                    .foregroundStyle(Ink.primary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                HStack(spacing: Space.x2) {
                    if let chip = StateChip.Kind(snapshot.status) {
                        StateChip(kind: chip)
                    }
                    if let feed = snapshot.source_feed {
                        Text(feed.title).gulpLabel()
                    }
                }
            }
            Spacer(minLength: Space.x2)

            // Packs only generate on an explicit trigger, so without this a
            // week away from a laptop leaves everything untouched (spec §2.1).
            if snapshot.status == .unprocessed {
                Button(action: start) {
                    Text("Start")
                        .font(GulpFont.labelSmall)
                        .tracking(0.8)
                        .textCase(.uppercase)
                        .foregroundStyle(Ink.primary)
                        .padding(.horizontal, Space.x3)
                        .frame(height: 32)
                        .overlay(
                            RoundedRectangle(cornerRadius: Radius.sm, style: .continuous)
                                .stroke(Ink.lineStrong, lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.vertical, Space.x3)
        .frame(minHeight: 44)
    }
}

private struct EmptyPeek: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Space.x3) {
            Text("Nothing forwarded yet").gulpLabel()
            Text("Share anything to Gulp from another app and it lands here.")
                .font(GulpFont.body)
                .foregroundStyle(Ink.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Loading

/// Skeletons matching the final layout, never a spinner on blank (`03 §8`).
private struct TodaySkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Space.x4) {
            RoundedRectangle(cornerRadius: Radius.xl, style: .continuous)
                .fill(Ink.fill)
                .frame(height: 196)
            ForEach(0 ..< 2, id: \.self) { _ in
                RoundedRectangle(cornerRadius: Radius.sm, style: .continuous)
                    .fill(Ink.fill)
                    .frame(height: 44)
            }
        }
        .accessibilityLabel("Loading today")
    }
}

extension StateChip.Kind {
    init?(_ status: Components.Schemas.SnapshotStatus) {
        switch status {
        case .ready: self = .ready
        case .processing, .queued: self = .processing
        case .unprocessed, .exported: self = .unprocessed
        case .needs_attention: self = .needsAttention
        }
    }
}
