import Testing
import Foundation
@testable import Gulp

/// Guards the two shapes Python's `datetime.isoformat()` actually produces.
/// This needs no server, so it runs in every `just ios-test`.
@Suite("Timestamps from a Python API")
struct DateTranscoderTests {
    private let transcoder = FlexibleISO8601()

    @Test func acceptsMicroseconds() throws {
        let date = try transcoder.decode("2026-06-24T08:34:55.277172Z")
        #expect(abs(date.timeIntervalSince1970 - 1_782_290_095.277172) < 0.001)
    }

    /// `isoformat()` drops the fraction when microseconds are exactly zero,
    /// so this shape appears on the same field as the one above.
    @Test func acceptsNoFraction() throws {
        let date = try transcoder.decode("2026-06-24T08:34:55Z")
        #expect(abs(date.timeIntervalSince1970 - 1_782_290_095) < 0.001)
    }

    @Test func acceptsAnOffsetRatherThanZulu() throws {
        let zulu = try transcoder.decode("2026-06-24T08:34:55Z")
        let offset = try transcoder.decode("2026-06-24T10:34:55+02:00")
        #expect(zulu == offset)
    }

    @Test func roundTrips() throws {
        let original = try transcoder.decode("2026-06-24T08:34:55.277172Z")
        let encoded = try transcoder.encode(original)
        let again = try transcoder.decode(encoded)
        #expect(abs(original.timeIntervalSince(again)) < 0.001)
    }

    @Test func refusesSomethingElse() {
        #expect(throws: DecodingError.self) {
            try transcoder.decode("last Tuesday")
        }
    }
}
