import SwiftUI
import GulpAPI

/// The shelf. On a phone this tab answers one question — *where did I put
/// that* — so search leads and the filters are a quiet mono row rather than a
/// bank of pills (spec §2.4).
///
/// **The `Due` tick column is missing**, and not by choice: `LibraryOut.items`
/// carries no per-item card or due count, and asking per row would be one
/// request per row. Two integers on that payload would restore the one thing
/// this screen was designed around. Recorded in the spec's API-gaps section.
struct LibraryView: View {
    @Environment(AppModel.self) private var model

    @State private var query = ""
    @State private var filter: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                Text("Library")
                    .font(GulpFont.screenTitle)
                    .foregroundStyle(Ink.primary)

                SearchField(text: $query).padding(.top, Space.x4)

                if !filters.isEmpty {
                    FilterRow(filters: filters, selected: $filter).padding(.top, Space.x1)
                }

                switch model.libraryLoad {
                case .idle, .loading:
                    LibrarySkeleton().padding(.top, Space.x4)
                case let .failed(message):
                    InlineError(message: message).padding(.top, Space.x6)
                case .loaded:
                    if visible.isEmpty {
                        EmptyShelf(searching: !query.isEmpty).padding(.top, Space.x8)
                    } else {
                        ForEach(Array(visible.enumerated()), id: \.element.id) { index, item in
                            if index > 0 {
                                Rectangle().fill(Ink.line).frame(height: 1)
                            }
                            LibraryRow(snapshot: item)
                        }
                        .padding(.top, Space.x2)
                    }
                }
            }
            .padding(.horizontal, Space.x5)
            .padding(.bottom, Space.x10)
        }
        .background(Ink.paper)
        .task { await model.refreshLibrary() }
        .refreshable { await model.refreshLibrary() }
    }

    /// Feeds first, then the user's own tags — the web sidebar's Sources and
    /// Mine groups, flattened to one row.
    private var filters: [String] {
        let feeds = model.library.compactMap { $0.source_feed?.title }
        let tags = model.library.flatMap(\.tags)
        return Array(Set(feeds)).sorted() + Array(Set(tags)).sorted()
    }

    private var visible: [Components.Schemas.SnapshotOut] {
        model.library.filter { item in
            let matchesFilter = filter.map { candidate in
                item.source_feed?.title == candidate || item.tags.contains(candidate)
            } ?? true
            let matchesQuery = query.isEmpty
                || item.title.localizedCaseInsensitiveContains(query)
            return matchesFilter && matchesQuery
        }
    }
}

private struct SearchField: View {
    @Binding var text: String

    var body: some View {
        HStack(spacing: Space.x2) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 15))
                .foregroundStyle(Ink.muted)
            TextField("Search everything you've kept", text: $text)
                .font(GulpFont.body)
                .foregroundStyle(Ink.primary)
                .tint(Ink.primary)
                .autocorrectionDisabled()
            if !text.isEmpty {
                Button { text = "" } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(Ink.muted)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, Space.x3)
        .frame(height: 44)
        .overlay(
            RoundedRectangle(cornerRadius: Radius.md, style: .continuous)
                .stroke(Ink.line, lineWidth: 1)
        )
    }
}

/// Mono labels, the active one inked and underlined — no pills.
private struct FilterRow: View {
    let filters: [String]
    @Binding var selected: String?

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Space.x4) {
                label("All", isOn: selected == nil) { selected = nil }
                ForEach(filters, id: \.self) { name in
                    label(name, isOn: selected == name) {
                        selected = selected == name ? nil : name
                    }
                }
            }
            .padding(.vertical, Space.x3)
        }
    }

    private func label(_ text: String, isOn: Bool, tap: @escaping () -> Void) -> some View {
        Button(action: tap) {
            VStack(spacing: 3) {
                Text(text)
                    .font(GulpFont.label)
                    .tracking(0.88)
                    .textCase(.uppercase)
                    .foregroundStyle(isOn ? Ink.primary : Ink.muted)
                Rectangle()
                    .fill(isOn ? Ink.primary : .clear)
                    .frame(height: 2)
            }
            .fixedSize()
            .frame(minHeight: 38)
        }
        .buttonStyle(.plain)
    }
}

private struct LibraryRow: View {
    let snapshot: Components.Schemas.SnapshotOut

    var body: some View {
        HStack(spacing: Space.x3) {
            VStack(alignment: .leading, spacing: Space.x2) {
                Text(snapshot.title)
                    .font(GulpFont.rowTitle)
                    .foregroundStyle(Ink.primary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                HStack(spacing: Space.x2) {
                    if let feed = snapshot.source_feed {
                        Text(feed.title).gulpLabel()
                    }
                    if snapshot.status != .ready, let chip = StateChip.Kind(snapshot.status) {
                        StateChip(kind: chip)
                    }
                }
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(Ink.muted)
        }
        .padding(.vertical, Space.x4)
        .frame(minHeight: 44)
        .contentShape(Rectangle())
    }
}

private struct EmptyShelf: View {
    let searching: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Space.x3) {
            Text(searching ? "Nothing matches" : "Nothing here yet").gulpLabel()
            Text(searching
                 ? "Try a different word, or clear the search."
                 : "Anything you forward shows up here once it's been digested.")
                .font(GulpFont.body)
                .foregroundStyle(Ink.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct LibrarySkeleton: View {
    var body: some View {
        VStack(spacing: Space.x4) {
            ForEach(0 ..< 5, id: \.self) { _ in
                RoundedRectangle(cornerRadius: Radius.sm, style: .continuous)
                    .fill(Ink.fill)
                    .frame(height: 44)
            }
        }
        .accessibilityLabel("Loading your library")
    }
}
