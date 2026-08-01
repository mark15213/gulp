import SwiftUI
import GulpAPI

/// Where the mastery bar landed after Today evicted it, with the right
/// neighbours: figures that only make sense over weeks (spec §2.5).
///
/// Colour is legitimate here — the five mastery states are shared spine and
/// this is the one screen whose whole job is reporting them.
struct YouView: View {
    @Environment(Auth.self) private var auth
    @Environment(AppModel.self) private var model

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                Text("You")
                    .font(GulpFont.screenTitle)
                    .foregroundStyle(Ink.primary)

                if let user = auth.user {
                    VStack(alignment: .leading, spacing: Space.x2) {
                        Text("Signed in").gulpLabel()
                        Text(user.display_name ?? user.email).gulpData(14)
                    }
                    .padding(Space.x4)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .gulpCard()
                    .padding(.top, Space.x4)
                }

                if let mastery = model.today?.mastery {
                    MasterySection(mastery: mastery)
                        .padding(.top, Space.x8)
                }

                SessionLength().padding(.top, Space.x8)

                Button {
                    Task { await auth.signOut() }
                } label: {
                    HStack {
                        Text("Sign out").font(GulpFont.body).foregroundStyle(Ink.primary)
                        Spacer()
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                            .font(.system(size: 14))
                            .foregroundStyle(Ink.muted)
                    }
                    .frame(height: 52)
                }
                .buttonStyle(.plain)
                .padding(.top, Space.x6)
                .overlay(alignment: .top) {
                    Rectangle().fill(Ink.line).frame(height: 1).offset(y: Space.x6)
                }

                Text("Tags, feeds and AI keys live on the web")
                    .gulpLabel()
                    .padding(.top, Space.x4)
            }
            .padding(.horizontal, Space.x5)
            .padding(.bottom, Space.x10)
        }
        .background(Ink.paper)
        .task { await model.refreshToday() }
    }
}

private struct MasterySection: View {
    let mastery: Components.Schemas.MasteryTally

    private var total: Int { max(1, mastery.`new` + mastery.learning + mastery.known) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Mastery").gulpLabel()
                Spacer()
                HStack(spacing: 4) {
                    Text("\(mastery.`new` + mastery.learning + mastery.known)").gulpData(11)
                    Text("cards").gulpLabel()
                }
            }

            GeometryReader { geometry in
                HStack(spacing: 3) {
                    segment(mastery.`new`, Mastery.new, in: geometry.size.width)
                    segment(mastery.learning, Mastery.learning, in: geometry.size.width)
                    segment(mastery.known, Mastery.known, in: geometry.size.width)
                }
            }
            .frame(height: 10)
            .padding(.top, Space.x3)

            HStack(spacing: Space.x5) {
                legend("New", mastery.`new`, Mastery.new)
                legend("Learning", mastery.learning, Mastery.learning)
                legend("Known", mastery.known, Mastery.known)
                Spacer(minLength: 0)
            }
            .padding(.top, Space.x3)

            if mastery.at_risk > 0 {
                HStack(spacing: Space.x2) {
                    Circle().fill(Mastery.atRisk).frame(width: 7, height: 7)
                    Text("\(mastery.at_risk)").gulpData(13)
                    Text("at risk of slipping").font(GulpFont.bodyS).foregroundStyle(Ink.secondary)
                }
                .padding(.top, Space.x3)
            }
        }
    }

    private func segment(_ count: Int, _ color: Color, in width: CGFloat) -> some View {
        Capsule()
            .fill(color)
            .frame(width: max(count == 0 ? 0 : 6, width * CGFloat(count) / CGFloat(total)))
    }

    private func legend(_ label: String, _ count: Int, _ color: Color) -> some View {
        HStack(spacing: Space.x2) {
            RoundedRectangle(cornerRadius: 2).fill(color).frame(width: 7, height: 7)
            Text("\(count)").gulpData(13)
            Text(label).font(GulpFont.caption).foregroundStyle(Ink.secondary)
        }
        .fixedSize()
    }
}

/// There is no endpoint to persist this — `gulp_session_minutes` is read-only
/// over the API — but `POST /sessions` takes `target_minutes` per session, so
/// the choice is honoured. It just does not follow you to the web app.
private struct SessionLength: View {
    @Environment(AppModel.self) private var model
    private let options = [5, 10, 15]

    var body: some View {
        VStack(alignment: .leading, spacing: Space.x3) {
            Text("Daily session").gulpLabel()
            HStack(spacing: 3) {
                ForEach(options, id: \.self) { minutes in
                    Button {
                        model.sessionMinutes = minutes
                    } label: {
                        HStack(spacing: 3) {
                            Text("\(minutes)").gulpData(12, color: isOn(minutes) ? Ink.primary : Ink.secondary)
                            Text("min").gulpLabel(isOn(minutes) ? Ink.primary : Ink.muted)
                        }
                        .frame(maxWidth: .infinity)
                        .frame(height: 38)
                        .background(isOn(minutes) ? Ink.surface : .clear)
                        .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(3)
            .background(Ink.fill)
            .clipShape(RoundedRectangle(cornerRadius: Radius.md, style: .continuous))
        }
    }

    private func isOn(_ minutes: Int) -> Bool { model.sessionMinutes == minutes }
}
