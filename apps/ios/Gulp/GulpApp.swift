import SwiftUI

@main
struct GulpApp: App {
    @State private var auth = Auth()
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(auth)
                .environment(model)
                // One place learns about a dead session; every screen just
                // observes the result.
                .task { model.attach(auth: auth) }
        }
    }
}
