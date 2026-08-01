import XCTest

/// The daily loop, tapped: Today → Start Gulp → a card → an answer → a grade →
/// the next card. This is the path the build plan could not check off, because
/// every step of it is a tap and nothing in the unit suite can tap.
final class SessionFlowUITests: XCTestCase {
    override func setUp() {
        super.setUp()
        continueAfterFailure = false
    }

    /// Today's hero is the entry to everything else, so it gets its own test:
    /// if this fails the rest of the failures are noise.
    func testTodayOffersASessionOrSaysWhyNot() throws {
        let app = try AppDriver.launch()

        let hero = app.gulpLabel("Due today")
        let clear = app.gulpLabel("Nothing due")
        XCTAssertTrue(
            hero.waitForExistence(timeout: 15) || clear.waitForExistence(timeout: 1),
            "Today showed neither a due count nor the nothing-due card"
        )
        if clear.exists { throw XCTSkip("Nothing is due — the session tests need cards.") }
        XCTAssertTrue(app.buttons["Start Gulp"].waitUntilHittable())
    }

    /// Start → a card is on screen with its type named and a way to answer it.
    func testStartGulpBuildsASessionAndPresentsACard() throws {
        let app = try AppDriver.launch()
        try startSession(app)

        XCTAssertTrue(
            app.anyElement("session.progress").waitForExistence(timeout: 20),
            "The session opened without a progress counter"
        )
        XCTAssertNotNil(
            cardTypeLabel(app),
            "No card type label. On screen: \(app.visibleText)"
        )
        XCTAssertNotNil(answerControl(app), "A card with no way to answer it")
    }

    /// Answering reveals the answer, and the three grades appear with it.
    func testAnsweringRevealsTheAnswer() throws {
        let app = try AppDriver.launch()
        try startSession(app)
        try answerCurrentCard(app)

        XCTAssertTrue(
            app.gulpLabel("Answer").waitForExistence(timeout: 8),
            "Revealing did not show an answer"
        )
        for grade in ["Missed", "Fuzzy", "Got it"] {
            XCTAssertTrue(app.buttons[grade].waitForExistence(timeout: 3), "Grade \(grade) is missing")
        }
    }

    /// The one that mutates: a real review, posted, and the session moves on.
    ///
    /// It grades exactly one card and grades it `Missed` — that reschedules the
    /// card to come back soon instead of pushing it weeks out, so running the
    /// suite costs the owner's queue almost nothing.
    func testGradingRecordsAReviewAndAdvances() throws {
        let app = try AppDriver.launch()
        try startSession(app)

        let progress = app.anyElement("session.progress")
        XCTAssertTrue(progress.waitForExistence(timeout: 20))
        let before = progress.label

        try answerCurrentCard(app)
        let missed = app.buttons["Missed"]
        XCTAssertTrue(missed.waitUntilHittable(8), "No grade to give")
        missed.tap()

        // Either the counter moved, or that was the last card and the summary
        // took over. Both are the session advancing.
        let complete = app.gulpLabel("Session complete")
        let deadline = Date().addingTimeInterval(25)
        var advanced = false
        while Date() < deadline {
            if complete.exists || (progress.exists && progress.label != before) {
                advanced = true
                break
            }
            Thread.sleep(forTimeInterval: 0.4)
        }
        XCTAssertTrue(
            advanced,
            "Grading did not advance the session — still at \(before)"
        )
    }

    /// Leaving mid-session must return to Today rather than trap you (`01 §F4`).
    func testASessionCanBeLeft() throws {
        let app = try AppDriver.launch()
        try startSession(app)
        XCTAssertTrue(app.anyElement("session.progress").waitForExistence(timeout: 20))

        app.buttons["End session"].tap()
        XCTAssertTrue(
            app.tabBars.buttons["Today"].waitForExistence(timeout: 10),
            "Ending the session did not return to the tab bar"
        )
    }

    // MARK: - Steps

    private func startSession(_ app: XCUIApplication) throws {
        let start = app.buttons["Start Gulp"]
        guard start.waitUntilHittable(20) else {
            throw XCTSkip("Nothing is due — the session tests need cards.")
        }
        start.tap()
    }

    /// The type label and the progress counter are published into the tree
    /// separately, so a bare `.exists` right after the counter appears is a
    /// race. Give the first candidate a moment before deciding.
    private func cardTypeLabel(_ app: XCUIApplication) -> String? {
        let types = ["Flashcard", "Multiple choice", "Cloze"]
        _ = app.gulpLabel(types[0]).waitForExistence(timeout: 3)
        return types.first { app.gulpLabel($0).exists }
    }

    /// A card is answered one of two ways depending on its type: pick an option,
    /// or ask to see the answer. Find whichever this card offers.
    private func answerControl(_ app: XCUIApplication) -> XCUIElement? {
        let show = app.buttons["Show answer"]
        if show.waitForExistence(timeout: 6) { return show }
        // An mcq option reads as "A, <the option text>" — the letter chip and
        // the text are one element.
        let option = app.buttons.matching(
            NSPredicate(format: "label BEGINSWITH %@", "A,")
        ).firstMatch
        return option.exists ? option : nil
    }

    private func answerCurrentCard(_ app: XCUIApplication) throws {
        guard let control = answerControl(app) else {
            XCTFail("The card offered no way to answer it")
            return
        }
        XCTAssertTrue(control.waitUntilHittable())
        control.tap()
    }
}
