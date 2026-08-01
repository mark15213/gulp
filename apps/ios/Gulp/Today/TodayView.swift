import SwiftUI

/// Task 4 builds the real screen — hero card, tick gauge, recently-forwarded
/// rows. What is here now is the minimum that proves the shell's plumbing:
/// the model fetched, this view only observed, and starting a session covers
/// the whole shell.
struct TodayView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: Space.x5) {
            Text(Date.now, format: .dateTime.weekday(.abbreviated).month(.abbreviated).day())
                .gulpLabel(Ink.secondary)

            switch model.todayLoad {
            case .idle, .loading:
                Text("—").gulpData(68)
            case let .failed(message):
                InlineError(message: message)
            case .loaded:
                Text("\(model.today?.due_count ?? 0)").gulpData(68)
                DueGauge(
                    new: model.today?.new_count ?? 0,
                    reviews: max(0, (model.today?.due_count ?? 0) - (model.today?.new_count ?? 0))
                )
            }

            PrimaryButton(title: "Start Gulp", systemImage: "arrow.right") {
                model.sessionIsRunning = true
            }

            Spacer()
        }
        .padding(.horizontal, Space.x5)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Ink.paper)
        .refreshable { await model.refreshToday() }
    }
}
