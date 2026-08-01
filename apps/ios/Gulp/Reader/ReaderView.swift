import SwiftUI
import GulpAPI

/// The pack **is** the screen: no `Read · Pack · Cards` control, the original
/// opens through the origin arrow, and the two things this screen can do sit
/// in the thumb zone (spec §2.6, `03 §7.6` as amended).
struct ReaderView: View {
    @Environment(Auth.self) private var auth
    @Environment(\.dismiss) private var dismiss

    let snapshot: Components.Schemas.SnapshotOut
    @State private var model: ReaderModel?
    @State private var showingChat = false

    var body: some View {
        ZStack {
            Ink.paper.ignoresSafeArea()
            if let model {
                switch model.load {
                case .idle, .loading:
                    ProgressView().tint(Ink.muted)
                case let .failed(message):
                    VStack(spacing: Space.x4) {
                        InlineError(message: message)
                        if let url = snapshot.origin_url, let link = URL(string: url) {
                            Link("Open the original", destination: link)
                                .font(GulpFont.rowTitle)
                                .foregroundStyle(Ink.primary)
                        }
                    }
                    .padding(.horizontal, Space.x5)
                case .loaded:
                    loaded(model)
                }
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text(snapshot.title).gulpLabel(Ink.secondary).lineLimit(1)
            }
            ToolbarItem(placement: .topBarTrailing) {
                if let url = snapshot.origin_url, let link = URL(string: url) {
                    Link(destination: link) {
                        Image(systemName: "arrow.up.forward.square")
                            .foregroundStyle(Ink.secondary)
                    }
                    .accessibilityLabel("Open the original")
                }
            }
        }
        .task {
            guard model == nil else { return }
            let reader = ReaderModel(snapshotID: snapshot.id, auth: auth)
            model = reader
            await reader.load()
        }
        .sheet(isPresented: $showingChat) {
            if let model {
                ChatView(model: model)
            }
        }
    }

    @ViewBuilder
    private func loaded(_ model: ReaderModel) -> some View {
        VStack(spacing: 0) {
            ScrollView {
                PackBody(pack: model.pack, snapshot: snapshot) { blockID in
                    model.attachedBlockID = blockID
                    showingChat = true
                }
                .padding(.horizontal, Space.x5)
                .padding(.bottom, Space.x8)
            }
            BottomBar(cards: nil) { showingChat = true }
        }
    }
}

// MARK: - The pack

private struct PackBody: View {
    let pack: Components.Schemas.PackOut?
    let snapshot: Components.Schemas.SnapshotOut
    let ask: (String?) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: Space.x2) {
                if let feed = snapshot.source_feed { Text(feed.title).gulpLabel() }
                Text(snapshot.created_at, format: .dateTime.year()).gulpLabel()
            }
            .padding(.top, Space.x3)

            Text(pack?.title ?? snapshot.title)
                .font(.system(size: 25, weight: .semibold))
                .foregroundStyle(Ink.primary)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, Space.x3)

            if let summary = pack?.summary {
                Text(summary)
                    .font(GulpFont.body)
                    .foregroundStyle(Ink.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, Space.x3)
            }

            // The one piece of special typography in the app: it is the single
            // line the pack exists to produce.
            if let insight = pack?.key_insight {
                VStack(alignment: .leading, spacing: Space.x3) {
                    Text("Key insight").gulpLabel()
                    Text(insight)
                        .font(.system(size: 16.5, weight: .medium))
                        .foregroundStyle(Ink.primary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.vertical, Space.x4)
                .frame(maxWidth: .infinity, alignment: .leading)
                .overlay(alignment: .top) { Rectangle().fill(Ink.line).frame(height: 1) }
                .overlay(alignment: .bottom) { Rectangle().fill(Ink.line).frame(height: 1) }
                .padding(.top, Space.x5)
            }

            // Contributions are a set, not a sequence — hairlines, no numbers.
            if let contributions = pack?.core_contributions, !contributions.isEmpty {
                Text("Contributions").gulpLabel().padding(.top, Space.x6)
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(contributions.enumerated()), id: \.offset) { index, text in
                        if index > 0 { Rectangle().fill(Ink.line).frame(height: 1) }
                        Text(text)
                            .font(GulpFont.bodyS)
                            .foregroundStyle(Ink.primary)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, Space.x3)
                    }
                }
                .padding(.top, Space.x2)
            }

            ForEach(pack?.sections ?? [], id: \.id) { section in
                if let heading = section.heading {
                    Text(heading)
                        .font(GulpFont.label)
                        .tracking(0.88)
                        .textCase(.uppercase)
                        .foregroundStyle(Ink.primary)
                        .padding(.top, Space.x8)
                }
                ForEach(Array(section.blocks.enumerated()), id: \.offset) { _, block in
                    BlockView(block: block, ask: ask)
                }
            }

            if let references = pack?.references, !references.isEmpty {
                Text("Worth following").gulpLabel().padding(.top, Space.x8)
                VStack(alignment: .leading, spacing: Space.x3) {
                    ForEach(Array(references.enumerated()), id: \.offset) { _, reference in
                        VStack(alignment: .leading, spacing: Space.x1) {
                            Text(reference.citation)
                                .font(GulpFont.bodyS)
                                .foregroundStyle(Ink.primary)
                            Text(reference.why_interesting)
                                .font(GulpFont.caption)
                                .foregroundStyle(Ink.secondary)
                        }
                        .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(.top, Space.x3)
            }
        }
    }
}

/// Every block type the `PaperPack` contract can produce, at 324 pt.
private struct BlockView: View {
    let block: Components.Schemas.PackSectionOut.blocksPayloadPayload
    let ask: (String?) -> Void

    var body: some View {
        Group {
            switch block {
            case let .prose(prose):
                Text(prose.content)
                    .font(GulpFont.body)
                    .foregroundStyle(Ink.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, Space.x3)
                    .contextMenu { askButton(prose.id) }

            case let .formula(formula):
                // Its own well, scrolling sideways on its own so the page
                // never does.
                ScrollView(.horizontal, showsIndicators: false) {
                    Text(formula.latex)
                        .font(GulpFont.data(13))
                        .foregroundStyle(Ink.primary)
                        .padding(.horizontal, Space.x3)
                        .padding(.vertical, Space.x4)
                }
                .frame(maxWidth: .infinity)
                .background(Ink.fill)
                .clipShape(RoundedRectangle(cornerRadius: Radius.md, style: .continuous))
                .padding(.top, Space.x4)
                .contextMenu { askButton(formula.id) }

            case let .figure(figure):
                VStack(spacing: Space.x3) {
                    if let urlString = figure.url, let url = URL(string: urlString) {
                        AsyncImage(url: url) { image in
                            image.resizable().scaledToFit()
                        } placeholder: {
                            RoundedRectangle(cornerRadius: Radius.md).fill(Ink.fill).frame(height: 140)
                        }
                    }
                    Text(figure.label).gulpLabel()
                }
                .padding(.top, Space.x4)
                .contextMenu { askButton(figure.id) }

            case let .list(list):
                VStack(alignment: .leading, spacing: Space.x2) {
                    ForEach(Array(list.items.enumerated()), id: \.offset) { index, item in
                        HStack(alignment: .firstTextBaseline, spacing: Space.x2) {
                            Text((list.ordered ?? false) ? "\(index + 1)." : "·").gulpData(13, color: Ink.muted)
                            Text(item)
                                .font(GulpFont.bodyS)
                                .foregroundStyle(Ink.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(.top, Space.x3)
                .contextMenu { askButton(list.id) }

            case let .table(table):
                ScrollView(.horizontal, showsIndicators: false) {
                    VStack(alignment: .leading, spacing: Space.x2) {
                        HStack(spacing: Space.x4) {
                            ForEach(Array(table.headers.enumerated()), id: \.offset) { _, header in
                                Text(header).gulpLabel().frame(minWidth: 70, alignment: .leading)
                            }
                        }
                        ForEach(Array(table.rows.enumerated()), id: \.offset) { _, row in
                            HStack(spacing: Space.x4) {
                                ForEach(Array(row.enumerated()), id: \.offset) { _, cell in
                                    Text(cell).font(GulpFont.caption)
                                        .foregroundStyle(Ink.secondary)
                                        .frame(minWidth: 70, alignment: .leading)
                                }
                            }
                        }
                    }
                    .padding(Space.x3)
                }
                .background(Ink.fill)
                .clipShape(RoundedRectangle(cornerRadius: Radius.md, style: .continuous))
                .padding(.top, Space.x4)
                .contextMenu { askButton(table.id) }

            case let .code(code):
                ScrollView(.horizontal, showsIndicators: false) {
                    Text(code.content)
                        .font(GulpFont.data(12))
                        .foregroundStyle(Ink.primary)
                        .padding(Space.x3)
                }
                .background(Ink.fill)
                .clipShape(RoundedRectangle(cornerRadius: Radius.md, style: .continuous))
                .padding(.top, Space.x4)
                .contextMenu { askButton(code.id) }
            }
        }
        // One stable anchor for every block type, so a UI test can reach the
        // long-press that opens block-scoped chat without guessing at copy.
        .accessibilityIdentifier("pack.block")
    }

    private func askButton(_ id: String) -> some View {
        Button {
            ask(id)
        } label: {
            Label("Ask about this", systemImage: "bubble.left")
        }
    }
}

private struct BottomBar: View {
    let cards: Int?
    let ask: () -> Void

    var body: some View {
        HStack(spacing: Space.x3) {
            Button(action: ask) {
                HStack(spacing: Space.x2) {
                    Image(systemName: "bubble.left").font(.system(size: 14))
                    Text("Ask about this").font(GulpFont.rowTitle)
                }
                .foregroundStyle(Ink.primary)
                .frame(maxWidth: .infinity)
                .frame(height: 44)
                .overlay(
                    RoundedRectangle(cornerRadius: Radius.md, style: .continuous)
                        .stroke(Ink.lineStrong, lineWidth: 1)
                )
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, Space.x4)
        .padding(.top, Space.x3)
        .padding(.bottom, Space.x2)
        .background(Ink.surface)
        .overlay(alignment: .top) { Rectangle().fill(Ink.line).frame(height: 1) }
    }
}
