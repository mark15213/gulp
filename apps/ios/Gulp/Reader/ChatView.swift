import SwiftUI
import GulpAPI

/// Anchored to the snapshot. Questions are bubbles; answers are plain text,
/// because an answer is read rather than said (spec §2.6).
struct ChatView: View {
    @Bindable var model: ReaderModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: Space.x5) {
                            if model.messages.isEmpty && !model.isAnswering {
                                EmptyThread()
                            }
                            ForEach(model.messages, id: \.id) { message in
                                MessageRow(message: message)
                            }
                            if !model.streaming.isEmpty {
                                Text(model.streaming)
                                    .font(GulpFont.body)
                                    .foregroundStyle(Ink.secondary)
                                    .fixedSize(horizontal: false, vertical: true)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .id("streaming")
                            } else if model.isAnswering {
                                ProgressView().tint(Ink.muted).id("streaming")
                            }
                        }
                        .padding(.horizontal, Space.x5)
                        .padding(.vertical, Space.x4)
                    }
                    .onChange(of: model.streaming) { _, _ in
                        withAnimation { proxy.scrollTo("streaming", anchor: .bottom) }
                    }
                }

                Composer(model: model)
            }
            .background(Ink.paper)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("Ask about this").gulpLabel(Ink.secondary)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                        .font(GulpFont.rowTitle)
                        .foregroundStyle(Ink.primary)
                }
            }
        }
    }
}

private struct MessageRow: View {
    let message: Components.Schemas.MessageOut

    var body: some View {
        if message.role == "user" {
            Text(message.content)
                .font(GulpFont.body)
                .foregroundStyle(Ink.primary)
                .padding(.horizontal, Space.x4)
                .padding(.vertical, Space.x3)
                .background(Ink.fill)
                .clipShape(
                    UnevenRoundedRectangle(
                        topLeadingRadius: Radius.lg,
                        bottomLeadingRadius: Radius.lg,
                        bottomTrailingRadius: 4,
                        topTrailingRadius: Radius.lg,
                        style: .continuous
                    )
                )
                .frame(maxWidth: .infinity, alignment: .trailing)
        } else {
            VStack(alignment: .leading, spacing: Space.x3) {
                Text(message.content)
                    .font(GulpFont.body)
                    .foregroundStyle(Ink.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                // Every answer carries the block it is grounded in.
                if !message.block_refs.isEmpty {
                    HStack(spacing: Space.x2) {
                        ForEach(message.block_refs.prefix(3), id: \.self) { reference in
                            Text(String(reference.prefix(8)))
                                .font(GulpFont.labelSmall)
                                .tracking(0.8)
                                .textCase(.uppercase)
                                .foregroundStyle(Ink.primary)
                                .padding(.horizontal, Space.x2)
                                .frame(height: 22)
                                .overlay(
                                    RoundedRectangle(cornerRadius: Radius.sm, style: .continuous)
                                        .stroke(Ink.lineStrong, lineWidth: 1)
                                )
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct Composer: View {
    @Bindable var model: ReaderModel

    var body: some View {
        VStack(alignment: .leading, spacing: Space.x2) {
            // The block you pulled in, always visible, always removable.
            if let attached = model.attachedBlockID {
                HStack(spacing: Space.x2) {
                    Text(String(attached.prefix(8)))
                        .font(GulpFont.labelSmall)
                        .tracking(0.8)
                        .textCase(.uppercase)
                        .foregroundStyle(Ink.primary)
                    Button { model.attachedBlockID = nil } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 10, weight: .medium))
                            .foregroundStyle(Ink.secondary)
                    }
                    .buttonStyle(.plain)
                }
                .padding(.horizontal, Space.x2)
                .frame(height: 26)
                .overlay(
                    RoundedRectangle(cornerRadius: Radius.sm, style: .continuous)
                        .stroke(Ink.lineStrong, lineWidth: 1)
                )
            }

            HStack(spacing: Space.x2) {
                TextField("Ask anything", text: $model.draft, axis: .vertical)
                    .font(GulpFont.body)
                    .foregroundStyle(Ink.primary)
                    .tint(Ink.primary)
                    .lineLimit(1 ... 4)
                    .padding(.leading, Space.x3)
                Button {
                    Task { await model.ask() }
                } label: {
                    Image(systemName: "arrow.up")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(Ink.surface)
                        .frame(width: 32, height: 32)
                        .background(model.draft.isEmpty ? Ink.muted : Ink.primary)
                        .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                }
                .buttonStyle(.plain)
                .disabled(model.draft.isEmpty || model.isAnswering)
                .padding(.trailing, 6)
            }
            .frame(minHeight: 44)
            .overlay(
                RoundedRectangle(cornerRadius: Radius.md, style: .continuous)
                    .stroke(Ink.line, lineWidth: 1)
            )
        }
        .padding(.horizontal, Space.x4)
        .padding(.top, Space.x3)
        .padding(.bottom, Space.x4)
        .background(Ink.surface)
        .overlay(alignment: .top) { Rectangle().fill(Ink.line).frame(height: 1) }
    }
}

private struct EmptyThread: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Space.x3) {
            Text("Nothing asked yet").gulpLabel()
            Text("Ask about anything in the pack. Answers cite the block they came from.")
                .font(GulpFont.body)
                .foregroundStyle(Ink.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
