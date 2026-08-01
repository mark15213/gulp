import XCTest

/// Shared setup for the tests that tap.
///
/// These drive the shipped app against a live API — the same one the unit
/// integration suite uses — because interaction is the half a unit test
/// structurally cannot reach. A model can be *asked* to grade a card; only a
/// tap proves the button exists, is hittable, and is wired to that model.
///
/// **These tests mutate real data.** Grading a card is a real review against
/// the dev database. `SessionFlowUITests` therefore grades exactly one card,
/// and grades it `Missed`, which schedules it to come back rather than pushing
/// it weeks out. Nothing else here writes.
enum AppDriver {
    static let email = "dev@example.com"
    static let password = "gulp-dev-2026"

    /// Reaches this process as `GULP_TEST_API` because the scheme sets
    /// `TEST_RUNNER_GULP_TEST_API` — a UI-test runner is a separate app, and
    /// only that prefix crosses into it (the prefix is stripped on the way).
    /// Unset means skip, never "fall back to a default": a UI test driving a
    /// server that isn't there passes for the wrong reason.
    static var apiBase: String? {
        ProcessInfo.processInfo.environment["GULP_TEST_API"]
    }

    static func launch() throws -> XCUIApplication {
        guard let apiBase else {
            throw XCTSkip("GULP_TEST_API is unset — run `just ios-uitest` with the API up.")
        }
        let app = XCUIApplication()
        app.launchArguments += ["-GulpBaseURL", apiBase]
        app.launch()
        try signInIfNeeded(app)
        return app
    }

    /// The login cookie lives in the App Group container, which usually
    /// survives a reinstall — so most runs land straight on Today. Handle the
    /// other case rather than depending on which one it is.
    private static func signInIfNeeded(_ app: XCUIApplication) throws {
        // Fast path first: waiting out the email field's timeout on every
        // launch would add ten seconds to every test in the suite.
        if app.tabBars.buttons["Today"].waitForExistence(timeout: 12) { return }

        let emailField = app.textFields["Email"]
        guard emailField.waitForExistence(timeout: 5) else { return }

        emailField.tap()
        emailField.typeText(email)
        let passwordField = app.secureTextFields["Password"]
        passwordField.tap()
        passwordField.typeText(password)
        app.buttons["Sign in"].tap()

        XCTAssertTrue(
            app.tabBars.buttons["Today"].waitForExistence(timeout: 15),
            "Signing in did not reach the tab bar"
        )
    }
}

extension XCUIElement {
    /// `waitForExistence` is not enough on its own: SwiftUI publishes elements
    /// into the tree before they are laid out, and tapping a zero-size element
    /// throws rather than failing an assertion.
    @discardableResult
    func waitUntilHittable(_ timeout: TimeInterval = 10) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if exists && isHittable { return true }
            Thread.sleep(forTimeInterval: 0.25)
        }
        return false
    }
}

extension XCUIApplication {
    /// Every small label in this app goes through `gulpLabel`, which applies
    /// `.textCase(.uppercase)`. That transform reaches the *accessibility*
    /// label only for `Text("a literal")` — a `Text(someString)` renders
    /// uppercase but is still published in its original case. So `Due today`
    /// arrives as `DUE TODAY` while the card type `Multiple choice` arrives
    /// unchanged. Match either.
    func gulpLabel(_ text: String) -> XCUIElement {
        staticTexts.matching(NSPredicate(format: "label ==[c] %@", text)).firstMatch
    }

    /// An `accessibilityIdentifier` on a SwiftUI container surfaces under
    /// whichever element type the framework decided on, which is not stable
    /// across a layout change. Ask for any type.
    func anyElement(_ identifier: String) -> XCUIElement {
        descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    /// What is actually on screen, for a failure message. A UI test that says
    /// only "not found" sends you to Xcode to look; one that lists what *was*
    /// there usually answers the question on the spot.
    var visibleText: String {
        staticTexts.allElementsBoundByIndex
            .prefix(30)
            .map(\.label)
            .filter { !$0.isEmpty }
            .joined(separator: " | ")
    }
}
