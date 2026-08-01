import SwiftUI

@main
struct GulpApp: App {
    @State private var auth = Auth()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(auth)
        }
    }
}
