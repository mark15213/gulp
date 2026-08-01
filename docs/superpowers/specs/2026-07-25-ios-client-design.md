# iOS client — design

*Gulp · client design · 2026-07-25 · brainstorm output*

> The first design pass at `apps/mobile`'s replacement: a **native SwiftUI iOS
> client** scoped to the consumption end — forward from anywhere, run the daily
> Gulp session, read what came back. Ten screens are drawn (Today · prompt ·
> reveal · summary · share sheet · Library · You · reader · reader-scrolled ·
> chat). The design costs `03` four amendments, all recorded in §5.
>
> **Correction (2026-08-01).** This spec claimed the API needs no server work.
> Building the client disproved it: four screens want a field the API does not
> expose (§3.2). None blocks the loop, but the claim was wrong and is retracted
> rather than quietly softened.
>
> Mockups: see the design artifact published with this spec.

## 0. Decisions locked in (owner-approved 2026-07-25)

- **Scope: pure consumption end.** Forward, Today, Gulp mode, read a pack,
  find something again. Deep curation, tag management, feeds, and AI settings
  stay on web. This is `01 §3`'s original split, unchanged.
- **Stack: native SwiftUI**, not Expo/React Native. The v1 value is
  concentrated in the share extension and in the feel of a daily ritual, which
  is precisely the layer RN makes hardest. Cost accepted: a second toolchain,
  a Swift client generated from the same `openapi.json`, and no Android.
  `apps/mobile` (the Expo placeholder) is superseded — see §7.
- **Navigation: three tabs** — `Today · Library · You`. The `⊕ Capture` tab
  from `01 §4.3` is demoted to a nav-bar button; with a share extension
  installed, "open the app first, then capture" is a path almost nobody walks,
  and a tab slot is too expensive for it.
- **Type: two families.** Inter for words, Geist Mono for every number, count,
  interval and uppercase label. Instrument Serif is cut.
- **Colour: paper and ink.** The primary action is ink; blue survives in exactly
  one place, the `Due` state — which on mobile means Library's tick marks;
  amber appears exactly once, on the streak.
- **Platform surfaces: share extension only.** No widget, no push, no offline
  in v1 (§6).
- **The phone can trigger processing.** A `Start` action on an unprocessed row
  in Today's recently-forwarded peek.

## 1. Why native, in one paragraph

`packages/ui` contains a `tokens.css` and an index — there is no cross-platform
component library to preserve, so "keep parity with web, don't fork the design
system" (the instruction the deleted `apps/mobile/CLAUDE.md` carried) reduces in
practice to sharing ~40 token values, which any stack can do. That removes the main argument for Expo. What
remains is a client whose two jobs are a share extension and a five-minute
daily ritual — native territory. The contract discipline of rule 2 survives
intact: Swift types are generated from the same `openapi.json` that produces
`packages/api-client`, so the data model stays the single source of truth.

## 2. Screens

### 2.1 Today

The daily home. Answers "what now" and nothing else.

| Region | Content | Source |
|---|---|---|
| Nav bar | `+` capture (secondary, opens the same sheet as the share extension) | |
| Overline | date · streak (amber flame + `N DAYS`) | `SummaryOut.streak_days` |
| Hero card | the due count as a large mono numeral, beside **N discrete tick marks** split into new / reviews, then **Start Gulp** (ink) | `due_count`, `new_count` |
| Recently forwarded | 3 rows: title, status chip, and — when `unprocessed` — a `Start` button | `recent[]` |

**The tick marks are the app's unit of work.** Twelve due cards render as
twelve marks, each group labelled underneath. The same mark returns as the
session progress rail (§2.2) and closes filled on the summary. This is the
design's one signature device and it encodes data rather than decorating it.

Fill carries one meaning everywhere it appears: **hairline means you have not
met this card yet, ink means you have.** So the gauge draws new cards hairline
and reviews ink, and the rail draws remaining cards hairline and answered ones
ink — the same rule, not two conventions that happen to look alike. Library is
the one place fill is coloured rather than ink, because there it is carrying the
`Due` state from the shared palette (§2.4).

**What is *not* here:** the mastery tally. It moved to `You` — `01 §2.4` scopes
Today to "what should I do right now", and `03 §7.9`'s Today inventory never
listed mastery in the first place. Removing it also removed three hues from the
screen (§4).

**The `Start` affordance.** Pack generation is manually triggered (`S2 §2.4`).
Without a trigger on the phone, anything forwarded away from a laptop stays
`unprocessed` indefinitely and the core loop silently breaks for the whole week
a user is mobile-first. One tap that fires an existing pipeline is not curation.
It needs no server work: `POST /snapshots/{id}/process` already exists.

### 2.2 Gulp session — three beats

`03 §7.7`'s hero flow. No tab bar, no title bar; one thing per screen.

1. **Prompt** — close button, `n / N` in mono, the tick rail, the card-type
   overline (`MULTIPLE CHOICE` / `FLASHCARD` / `CLOZE`), the prompt, and the
   options anchored in the thumb zone. Source stays hidden until reveal.
2. **Reveal & grade** — the chosen option marked, a `CORRECT` chip, then the
   explanation with the source it is grounded in. Three grade controls —
   `Missed · Fuzzy · Got it` — rendered as hairline pills with a single
   mastery-coloured dot each, **and the interval each grade buys printed
   underneath** (`TODAY` / `+1 D` / `+6 D`), from `ReviewOut.mastery.interval_days`.
   Making the scheduler legible at the moment of grading is new; the docs
   never asked for it and it costs nothing.
3. **Summary** — the rail closes full, then reviewed / newly known / still
   fuzzy / back tomorrow as mono figures, the streak (the only celebration the
   register allows), a "next" line pointing at real work, and `Done` /
   `Keep going`. Never a dead end (`01 §F4`).

`SessionOut.cards[]` carries `answer` and `explanation` up front, so reveal is
local — no round trip mid-session, and offline (§6) becomes a smaller job later
than it looks.

### 2.3 Share extension

The only platform extension in v1, and the reason native was chosen.

A bottom sheet over the host app: detected title, type chip, source host, an
optional note, optional tags, and a **Forward** button. It self-confirms after
~3 s, so the true path is share → done. Nothing waits on AI (`01 §2.1/2.2`).

The verb is **Forward**, never Gulp — forwarding is how things get in, gulping
is what you do with them later. Keeping the two apart is what stops the
product's name from meaning two things.

### 2.4 Library

Answers one question on a phone: *where did I put that*.

A hairline search field leads, then the filters as a row of mono labels — the
web's Sources / Mine tag sidebar flattened, single-select, the active one inked
and underlined. No icon column, no filled search well, no bank of pills: the
three stacked full-width bars a list screen accretes by default are removed and
type carries the structure instead.

Rows are `ready` snapshots — title (up to two lines), then source and card count
in mono. **The right edge carries the tick mark from §2.1: one tick, one card
due today, drawn in the shared `Due` blue `#2563EB`.** Three ticks means three cards want you; an empty right edge means
the item is at rest, and that emptiness is the reading. Scanning the column
sorts the shelf into live and dormant with nothing spent on words, and it costs
no new vocabulary — the mark already means the same thing on Today and in the
session rail.

The ticks are blue rather than ink because `Due` is blue in the mastery palette
that `03 §1.1` fixes as non-diverging spine; drawing due cards in ink would be
the same violation this design refused when it declined to re-tint the mastery
bar (§4). Three hairline marks in one hue carrying one meaning is also the only
form of colour the cut-down palette was ever trying to keep. Net effect:
**blue in this app means "there is work here", and nothing else.**

This is also how the screen satisfies `01 §2.3` ("every object has a mastery
state, and it is always visible"). The first draft buried the due count in a run
of mono metadata, where it was legible but not scannable.

*Considered and not taken:* splitting the list into "still working on" and "at
rest" sections. It buys a stronger focal point and lets resting rows show *when
you last read it* instead of a card count, which is closer to how people
actually recall an article. Rejected because grouping plus filtering is one
structure too many on a 324 pt screen — worth revisiting if the filter row turns
out to go unused.

Tapping a row opens the pack reader. That reader is not designed yet (§7).

### 2.5 You

Account, then the mastery bar Today evicted — with the right neighbours: streak,
best streak, total reviewed. Then the daily session length (`5 / 10 / 15 MIN`,
writing `SessionStartIn.target_minutes`), sign out, and a line naming what the
phone deliberately doesn't do ("Tags, feeds and AI keys live on the web").

Colour is legitimate here: the five mastery states are shared spine (`03 §1.1`)
and this is the one screen whose whole job is reporting them.

### 2.6 Pack reader and its chat

The largest screen, and read-only by scope.

**No `Read · Pack · Cards` segmented control** (§5.4). The pack *is* the screen;
the original opens through an origin arrow in the top bar; the card count sits
in the bottom bar beside `Ask about this`. Both bottom actions are in the thumb
zone, because they are the only two things this screen can do.

Reading order follows the `PaperPack` contract (`02 §4.4`): overline (source ·
year · reading time), title, `summary`, then **key insight** — given the one
piece of special typography in the app, a rule above and below and a heavier
setting, because it is the single line the pack exists to produce. **Core
contributions** are a *set*, not a sequence, so they are separated by hairlines
and carry no numbering. Body sections render `§ n.n` headings in mono, prose in
Inter, formulas in a tinted well that scrolls sideways on its own if it must,
and figures with their caption. The title moves into the top bar once the real
one scrolls away.

**Chat** is a full screen anchored to the snapshot, matching the web's
snapshot-scoped `PackMessage` model with `block_refs`. Questions are bubbles;
answers are plain text, because an answer is read rather than said. Every answer
carries the block it is grounded in as a tappable citation chip that scrolls the
reader to it, and any block pulled into the conversation sits above the composer
as a removable context chip.

Editing blocks stays on web (`03 §7.6`), as does card accept/reject.

## 3. API surface consumed

Everything the client needs already ships. No endpoint is added for v1.

| Screen | Endpoint |
|---|---|
| Today | `GET /today` |
| Today · Start | `POST /snapshots/{id}/process` |
| Session | `POST /sessions` · `GET /sessions/current` · `POST /sessions/{id}/reviews` · `/snooze` · `/complete` · `GET /sessions/{id}/summary` |
| Share extension | `POST /capture` |
| Library | `GET /library` |
| Reader | `GET /snapshots/{id}` · `GET /snapshots/{id}/pack` |
| Chat | `GET /snapshots/{id}/messages` · `POST /snapshots/{id}/messages/stream` (SSE) |
| You | `GET /me` · `POST /logout` |

## 3.1 Two things the contract does not survive on its own

Both were found by building the Swift client, not by reading the schema, and
both would have silently corrupted every screen downstream.

**Nullable fields vanish.** FastAPI writes an optional field as an OpenAPI 3.1
union with the null type — `anyOf: [{type: string}, {type: "null"}]`.
swift-openapi-generator 1.13 does not support `type: "null"` and drops the
**whole property**. On this API that is 73 fields, 34 of them required,
including `SessionCardOut.answer` and `.explanation` — the two the reveal
screen is built on (§2.2) — and the entire body of
`GET /gulp/sessions/current`, which generated as an empty struct.
`apps/ios/Tools/openapi_for_swift.py` rewrites each such union to its non-null
branch and drops the field from `required`, so it lands as a Swift optional:
the same meaning, in a shape the generator understands. It runs as the first
step of `just gen-client-swift` and is not optional.

**Timestamps come in two shapes.** `datetime.isoformat()` emits microseconds,
except when they are exactly zero, when it omits the fraction entirely. The
runtime's stock ISO8601 transcoder accepts one shape or the other, so roughly
one response in a million — and every response from a coarse clock — fails to
decode. `FlexibleISO8601` in `Net/GulpClient.swift` accepts both.

Neither needs a server change, but both are worth knowing before a third
client is written against this API.

## 3.2 Fields the design needs and the API does not expose

Found by building, in the order they were hit. None blocks the core loop; each
is a small addition to an existing payload.

| Screen | Wants | Today's answer |
|---|---|---|
| Today (§2.1) | a streak | `streak_days` exists only on `SummaryOut`, so it can only be shown just after a session. **Omitted.** One integer on `TodayOut` fixes it. |
| Library (§2.4) | per-item card and due counts | `LibraryOut.items` are bare `SnapshotOut`s. Asking per row is one request per row. **The tick column — the thing this screen was designed around — is absent.** Two integers per item fixes it. |
| You (§2.5) | to save the session length | `gulp_session_minutes` is read-only; there is no settings endpoint. Stored locally instead, and honoured, because `POST /sessions` takes `target_minutes` per session — it just does not follow you to web. |
| Session (§2.2) | to know there is no session | `GET /gulp/sessions/current` answers a literal `null` body, which the generated client cannot decode. Handled at the call site. **204 would fix it for every typed client.** |

The first two are the ones a user would notice.

## 4. Visual system — the mobile register as built

Tokens are `03 §3.2`'s mobile (warm) column, unchanged: `--bg #FAFAF7`,
`--surface #FFFFFF`, `--fill #F4F3EE`, `--border #E9E6DD`,
`--border-strong #D8D3C7`, `--muted #A8A395`, `--text-2 #6B665A`,
`--text-1 #1C1B18`. Radii 12 / 16 / 20, `--shadow-card 0 2px 8px rgba(28,27,24,.08)`,
4px spacing base, 44pt minimum targets.

What changed is the colour *budget*. The Today screen originally carried five
hues — blue (gradient + glow), amber, and the mastery bar's slate/amber/emerald
— plus two tinted status chips. Three cuts, in order of how much each bought:

1. **Removed the mastery bar from Today** → three hues gone at once, and the
   screen got closer to its spec'd job. Note the alternative was rejected on
   principle: re-tinting the mastery bar to an ink ramp would have violated
   `03 §1.1`, which fixes the mastery palette as never-diverging spine. The
   states may be *absent* from a screen; they may not be *recoloured*.
2. **Ink took the primary action** (§5.2) → the largest cold mass on a warm
   ground, gone.
3. **Status chips lost their tint** (§5.3) → hairline pill + coloured dot.

What survives: ink, paper, one amber streak, mastery colour where mastery is
the subject, and blue on `Due`.

## 5. Amendments required to `03-ui-system.md`

### 5.1 The voice loses its serif

`03 §2.3` assigns Instrument Serif the "voice" role (mobile hero moments);
`§4.2` rations it to one line per screen. **Cut.** Headlines go to Inter, the
large figures to Geist Mono. This is the stronger claim: `§2.3` already argues
that monospaced tabular figures are what make mastery read as *measured*, so
letting the numerals carry the hero moment is the system agreeing with itself.
Three families become two on mobile.

Scope note: `§10` asks whether the serif earns its place *on web*. This spec
does not decide that — but mobile hero moments were the serif's main home
(`§2.3` assigns it exactly there), so cutting it here leaves web with only
"occasional marketing headers". The web question is now nearly forced; it is
still the owner's to close.

### 5.2 Ink takes the primary action

`03 §1.2.2` states "blue means act"; `§2.1` states the registers differ in *how
much* blue, not *which* blue; `§1.1` lists "one blue, everywhere" as
non-diverging spine. **Amended.** On mobile the primary action is `--text-1`
ink — as is the active tab — and blue is reserved for the `Due` state alone,
which in the drawn screens means Library's tick marks and nothing else (§2.4).

The reasoning, and why it isn't special pleading: `#2563EB` is
`hsl(221, 83%, 53%)` while the entire mobile neutral family sits at hue 42–60 —
paper 60, ink 45, grey 42. A saturated, light, near-complementary blue laid on
warm paper reads as a sticker. `§3.2` already solves exactly this class of
problem by giving one semantic token two value maps (web cool, mobile warm);
this extends that established pattern to the brand colour. The spine claim
becomes "one blue **role**", not "one blue **value**".

*Considered and not taken:* warming the blue itself (indigo `#2F39C6`, denim
`#3A60A6`, ink-blue `#1E3B8A`). All three sit on the paper better than the
current value and all three clear contrast comfortably; ink-blue in particular
was close. They remain the fallback if blue must survive as the mobile brand
colour — the amendment cost is identical either way.

### 5.3 Status chips lose their tint

`03 §7.2` specifies a tinted pill with on-tint text. **Amended for mobile:**
hairline pill, `--text-2` label, one coloured dot. Colour plus label still
carries state, so `§9` holds; the anatomy now differs by register and the doc
should say so.

### 5.4 The phone loses its segmented control

`03 §7.6` gives mobile a stacked `Read · Pack · Cards` control. **Cut.** The web
reader already dropped its Original tab for an origin arrow in the 2026-07-10
redesign, and a read-only phone has even less reason to carry three modes. The
pack is the screen, the original is an arrow, the cards are a count.

## 6. Deferred (named, not forgotten)

- **Home / lock-screen widget** — `N due` + streak, deep-linking into a session.
- **Local notifications** — the daily reminder of `01 §F9`. Pure local
  scheduling; no server push infrastructure needed when it lands.
- **Offline Gulp** — `01 §10.4`. Cheaper than it looks (§2.2), still not v1.
- **CJK typography** — `03 §10` predicted mobile would host it first. Not v1;
  English/Latin only, per `03`'s stated scope.
- **Android** — out of scope by the native-Swift decision.
- **Conversation capture / sediment** (`01 §F5`) beyond the session's
  "Explain more" affordance.

## 7. Open questions

1. **Nothing brings the user back.** With no push and no widget, the daily
   ritual depends entirely on the user remembering. That is a deliberate v1
   call, but it leaves the streak on Today as the only re-engagement mechanic
   in the product. Worth settling before the first build, not after.
2. ~~**Sign-in has no shape yet.**~~ **Resolved 2026-07-25 — use the cookie.**
   `auth._set_cookie` sets `max_age = session_ttl_days * 86400`, so it is a
   persistent cookie rather than a session one and `HTTPCookieStorage` keeps it
   across launches; `POST /auth/login` needs no server change. Backing the store
   with `HTTPCookieStorage.sharedCookieStorage(forGroupContainerIdentifier:)`
   also gives the share extension the login for free, which a Keychain PAT would
   not without extra plumbing. See the plan, Task 2.
3. ~~**What happens to `apps/mobile`.**~~ **Resolved 2026-07-25.** The Xcode
   project lives at `apps/ios` — `apps/` groups clients by role, not by
   language, and pnpm skips workspace members without a `package.json`. The
   Expo placeholder is deleted. `just` grew `ios`, `ios-test` and
   `gen-client-swift`, the last folded into `gen-client` so the two generated
   clients cannot drift; it no-ops until the Swift package exists. Root
   `CLAUDE.md` rule 1 now reads *three* languages, and `05-repo-structure.md`
   §2/§5.3/§6.1/§7 are updated. Applied in the plan's Task 0.

## 8. Where this lands

`04 §5` sequences clients web-first and folds mobile in later as "a per-subsystem
parity pass". This design is that pass for `S0` (shell + nav), `S1` (capture),
and `S4` (session) simultaneously — which is the honest shape, since a phone
with only one of the three is not usable. `S3`'s library slice is included at
reading depth only; its KB/Concept remainder stays deferred, exactly as on web.
