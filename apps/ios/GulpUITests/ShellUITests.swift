import XCTest

/// The rest of the taps: moving between tabs, opening a pack, asking about a
/// block, and changing the one setting this client owns.
final class ShellUITests: XCTestCase {
    override func setUp() {
        super.setUp()
        continueAfterFailure = false
    }

    func testAllThreeTabsOpen() throws {
        let app = try AppDriver.launch()
        let tabs = app.tabBars.buttons

        tabs["Library"].tap()
        XCTAssertTrue(app.staticTexts["Library"].waitForExistence(timeout: 10))

        tabs["You"].tap()
        XCTAssertTrue(app.staticTexts["You"].waitForExistence(timeout: 10))

        tabs["Today"].tap()
        XCTAssertTrue(
            app.gulpLabel("Due today").waitForExistence(timeout: 10)
                || app.gulpLabel("Nothing due").exists,
            "Coming back to Today showed neither state"
        )
    }

    /// Library → a pack → back. Tapping a row is the only way into the reader
    /// from this tab, so this covers the navigation and the reader's load.
    func testALibraryRowOpensThePack() throws {
        let app = try AppDriver.launch()
        try openFirstPack(app)

        XCTAssertTrue(
            app.anyElement("pack.block").waitForExistence(timeout: 25)
                || app.gulpLabel("Key insight").exists
                || app.buttons["Ask about this"].exists,
            "The reader opened but rendered no pack"
        )
    }

    /// The bottom-bar ask, which is the snapshot-scoped conversation.
    func testTheReaderCanOpenChat() throws {
        let app = try AppDriver.launch()
        try openFirstPack(app)

        let ask = app.buttons["Ask about this"]
        guard ask.waitUntilHittable(25) else {
            throw XCTSkip("The pack never finished loading.")
        }
        ask.tap()

        // The sheet is up if there is somewhere to type. Nothing is sent —
        // asking would spend the owner's model credits for no extra coverage.
        XCTAssertTrue(
            app.textFields.firstMatch.waitForExistence(timeout: 10)
                || app.textViews.firstMatch.waitForExistence(timeout: 2),
            "The chat sheet opened with no input"
        )
    }

    /// Long-press a block → "Ask about this". A different code path from the
    /// bottom bar: it carries a block reference, so the answer is anchored to
    /// the passage rather than to the whole pack.
    func testLongPressingABlockOffersToAskAboutIt() throws {
        let app = try AppDriver.launch()
        try openFirstPack(app)

        guard let block = pressableBlock(app) else {
            throw XCTSkip("This pack rendered no blocks to press. On screen: \(app.visibleText)")
        }
        add(XCTAttachment(screenshot: app.screenshot()))
        block.press(forDuration: 1.2)

        // The menu item and the bottom bar share the title, so counting is what
        // distinguishes "the menu opened" from "the bar was always there".
        let asks = app.buttons.matching(identifier: "Ask about this")
        let deadline = Date().addingTimeInterval(8)
        while Date() < deadline && asks.count < 2 {
            Thread.sleep(forTimeInterval: 0.3)
        }
        XCTAssertGreaterThanOrEqual(
            asks.count, 2,
            "Long-pressing a block did not open the ask menu"
        )
    }

    /// The one preference this client keeps. It is stored locally because the
    /// API has no endpoint for it (spec §3.2), so "it survives a relaunch" is
    /// exactly the claim worth testing.
    func testSessionLengthSurvivesARelaunch() throws {
        let app = try AppDriver.launch()
        app.tabBars.buttons["You"].tap()
        XCTAssertTrue(app.gulpLabel("Daily session").waitForExistence(timeout: 12))

        let fifteen = minutesOption(app, "15")
        guard fifteen.waitUntilHittable() else {
            XCTFail("No 15 min option on You")
            return
        }
        fifteen.tap()

        app.terminate()
        app.launch()
        app.tabBars.buttons["You"].tap()
        XCTAssertTrue(
            app.gulpLabel("Daily session").waitForExistence(timeout: 20),
            "The session length row did not come back after a relaunch"
        )
        XCTAssertTrue(minutesOption(app, "15").exists)
    }

    /// Today's `+`. It was wired to nothing until this test existed — the
    /// button drew, took the tap and did not a thing, which no unit test can
    /// see and no amount of reading the model would have caught.
    ///
    /// This one writes: it really does forward, so a run leaves one item in the
    /// inbox. That is the point — a sheet that opens proves half of it.
    func testTheForwardButtonActuallyForwards() throws {
        let app = try AppDriver.launch()
        app.tabBars.buttons["Today"].tap()

        let plus = app.buttons["Forward something"]
        XCTAssertTrue(plus.waitUntilHittable(15), "No forward button on Today")
        plus.tap()

        let field = app.textFields["Paste a link, or some text"]
        XCTAssertTrue(
            field.waitForExistence(timeout: 8),
            "The + button opened nothing. On screen: \(app.visibleText)"
        )
        field.tap()
        // A real, tiny, always-up page. A made-up path would 404 in the
        // worker's metadata fetch and leave the run's item in needs_attention,
        // which reads as a product bug rather than as test litter.
        field.typeText("https://example.com/")

        let forward = app.buttons["Forward"]
        XCTAssertTrue(forward.waitUntilHittable(5))
        forward.tap()

        XCTAssertTrue(
            app.staticTexts["In your inbox"].waitForExistence(timeout: 20)
                || app.staticTexts["Saved — it'll send when you're back online"]
                    .waitForExistence(timeout: 1),
            "Forwarding neither landed nor queued. On screen: \(app.visibleText)"
        )
    }

    // MARK: - Steps

    /// The first block sits well below the fold — a pack leads with its title,
    /// summary, key insight and contributions — so existing is not the same as
    /// being reachable. Scroll until it is.
    private func pressableBlock(_ app: XCUIApplication) -> XCUIElement? {
        let tagged = app.anyElement("pack.block")
        guard tagged.waitForExistence(timeout: 25) else { return nil }

        let scroll = app.scrollViews.firstMatch
        for _ in 0 ..< 6 {
            if tagged.exists && tagged.isHittable { return tagged }
            guard scroll.exists else { break }
            scroll.swipeUp()
        }
        return tagged.exists && tagged.isHittable ? tagged : nil
    }

    private func minutesOption(_ app: XCUIApplication, _ minutes: String) -> XCUIElement {
        app.buttons.containing(
            NSPredicate(format: "label CONTAINS %@", minutes)
        ).firstMatch
    }

    private func openFirstPack(_ app: XCUIApplication) throws {
        app.tabBars.buttons["Library"].tap()
        guard let row = firstLibraryRow(app) else {
            throw XCTSkip("The library is empty on this account.")
        }
        row.tap()
    }

    /// A row is a `NavigationLink` around a title, so it surfaces as a button
    /// whose label starts with that title. The other buttons on this screen —
    /// the filter row and the clear-search cross — are short and uppercase,
    /// which is what tells them apart.
    ///
    /// Filtering happens in Swift rather than in an `NSPredicate`: XCTest's
    /// element queries only accept a small set of key paths, and `label.length`
    /// is not one of them — it throws at query time rather than matching
    /// nothing.
    private func firstLibraryRow(_ app: XCUIApplication) -> XCUIElement? {
        let rows = app.buttons
        guard rows.firstMatch.waitForExistence(timeout: 25) else { return nil }
        return rows.allElementsBoundByIndex.first { button in
            let label = button.label
            return label.count > 12
                && label.rangeOfCharacter(from: .lowercaseLetters) != nil
        }
    }
}
