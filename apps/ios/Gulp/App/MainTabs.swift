import SwiftUI

/// Three tabs, no capture tab: the share sheet is where things get forwarded
/// from, so a slot for "open the app first, then capture" would be paying a
/// fifth of the bar for a path almost nobody walks (spec §0).
struct MainTabs: View {
    @Environment(AppModel.self) private var model

    /// Deliberately not named `Tab` — SwiftUI's own `Tab` is the builder used
    /// below, and a nested type would shadow it.
    enum Screen: Hashable {
        case today, library, you
    }

    @State private var screen: Screen = .today

    var body: some View {
        @Bindable var model = model

        // `.tabItem` rather than the `Tab` builder: that one is iOS 18+, and
        // the floor here is 17 (plan Tech Stack). The system fills the
        // selected symbol for us, which is the pairing `03 §2.6` asks for.
        TabView(selection: $screen) {
            NavigationStack { TodayView() }
                .tabItem { Label("Today", systemImage: "drop") }
                .tag(Screen.today)
            NavigationStack { LibraryView() }
                .tabItem { Label("Library", systemImage: "square.stack") }
                .tag(Screen.library)
            NavigationStack { YouView() }
                .tabItem { Label("You", systemImage: "person") }
                .tag(Screen.you)
        }
        // Ink, not blue: the primary accent moved (spec §5.2).
        .tint(Ink.primary)
        .toolbarBackground(Ink.surface, for: .tabBar)
        .toolbarBackground(.visible, for: .tabBar)
        .task { await model.refreshToday() }
        // A session is full-bleed with no tab bar (`03 §7.7`). Presenting it
        // over the whole shell makes that structural, rather than something
        // each screen has to remember to do.
        .fullScreenCover(isPresented: $model.sessionIsRunning) {
            SessionView()
        }
    }
}
