# 01 — Interaction Spec

*Gulp · interaction specification · v3 · 2026-06-23*

> Companion to [`00-product-one-pager.md`](00-product-one-pager.md). The one-pager defines **what** Gulp is and **why**; this doc defines **how the user moves through it** — the flows, key screens, states, and transitions across **mobile and web**.
>
> **Altitude:** flow-level + key screens. It specifies user-visible behavior, not visual design (colors, type, components live in the design system) and not the data/API contract (that's a later doc). Where mobile and web diverge, the difference is called out inline.

---

## 1. Scope & reading guide

- **Covers:** the full product surface — capture, knowledge packs, the library/knowledge base, Gulp mode, conversation capture, feeds & digests, mastery & scheduling, onboarding, notifications.
- **Surfaces in scope:** mobile app (iOS + Android), responsive web app, and external capture targets (share sheet, WeChat forward, email-in). *(A browser extension is deferred — see §11.)*
- **Two first-class clients:** mobile and web are co-equal. Each flow lists its mobile and web shape. Capture is mobile-led; deep reading and library work are web-led; Gulp mode is identical in intent on both.
- **Out of scope (v1):** team/collaboration, public sharing, content marketplace, and any flow listed in §11.

---

## 2. Design principles for interaction

These are the rules every flow must obey. When a screen decision is ambiguous, resolve it toward these.

1. **Capture is one gesture.** From intent to "saved" must never exceed a single deliberate action. The user should be able to capture without opening the app, and without waiting for processing.
2. **Processing is asynchronous and invisible-until-ready.** The user never waits on AI. Capture confirms instantly; the knowledge pack fills in behind the scenes and notifies when ready.
3. **Every object has a mastery state, and it is always visible.** The user can always see whether something is *new*, *learning*, *known*, or *due* — the library is a training ground, not a graveyard.
4. **The daily loop is the home.** The default screen answers "what should I do right now?" in under 5 seconds, not "here is everything you saved."
5. **Conversations end in knowledge.** No chat is a dead end; exiting a conversation always offers to keep what was learned.
6. **One thing per screen in Gulp mode.** During a learning session, the UI shows exactly one prompt, full-bleed, no chrome competing for attention.
7. **Rich model, light surface.** Gulp keeps a full knowledge-tool model, but the user only ever has to learn the spine (§4.1). Depth (Concepts, feeds, knowledge bases, the full mastery ladder) is present but introduced through use, never front-loaded.
8. **Graceful degradation.** Offline, slow networks, failed extraction, and unsupported content each have a defined, non-blocking state (§10).

---

## 3. Surfaces & responsibilities

| Surface | Owns | Notes |
|---|---|---|
| **Mobile app** | Capture (share sheet), daily Gulp mode, notifications, batch-confirm of new captures, digest | Primary for ingestion and daily habit; **consumption end** |
| **Web app** | Deep reading, inbox triage & pack curation, library/knowledge-base work, feed management, long Gulp sessions | NotebookLM-style workspace; **management end** |
| **External targets** | WeChat forward, OS share sheet, `gulp@…` email-in | Headless capture → lands in Inbox |

**Sync model:** all surfaces read/write the same account state. Capture and mastery updates sync optimistically; conflicts resolve last-write-wins on scalar fields and union on collections (e.g., tags). A capture made offline queues locally and uploads on reconnect (§10.4).

---

## 4. Information architecture

### 4.1 The model in one line (the spine)

Gulp is conceptually rich, so the objects must read as **one pipeline**, not a pile of types. Everything maps to a single sentence:

> You **save** things → Gulp **digests** them → turns them into **practice** → tracks what you **master** → and lets you **organize** it.

| Step | Object(s) | What the user feels |
|---|---|---|
| **Save** | **Source** → Snapshot · Conversation · Subscription | "I put something in" |
| **Digest** | **Knowledge pack** | "It read it for me" |
| **Practice** | **Card** (inside Gulp mode) | "It tests me" |
| **Master** | **mastery state** + **Concept** | "It knows what I know, and how ideas connect" |
| **Organize** | **Knowledge base** | "Group by project" |

Read the object list below through this spine and the count stops mattering — each thing has exactly one job in the flow.

### 4.2 Core objects

The library is built from typed objects. Each is individually addressable, linkable, and (where it bears knowledge) carries a mastery state.

**`Source` is the umbrella — anything knowledge flows from.** It is abstract; you never create a bare "Source," you create one of its three forms, which differ by how they relate to time:

| Form (`kind`) | Nature | What it is |
|---|---|---|
| **Snapshot** | frozen | a captured, point-in-time item — article · PDF · video · podcast · note · screenshot — plus its stored content (so it survives link rot). The everyday "thing you gulped." |
| **Conversation** | interactive | a chat thread anchored to a Source/Concept/Card, plus the knowledge sedimented from it. |
| **Subscription** | streaming | a followed feed (RSS, newsletter, channel) that auto-emits Snapshots. |

Built **on top of** Sources:

- **Knowledge pack** — the AI-generated digest attached to a Snapshot (summary, background, terms, claims, counter-views, connections).
- **Card** — an atomic, testable unit (question/answer, cloze, explain, apply). The unit of Gulp mode and scheduling. *(A user-authored takeaway is just a free-form Card — there is no separate "Insight" object.)*
- **Concept** — a normalized idea/term/person/org that Cards and Sources attach to; the spine of the knowledge graph.

For **organization**:

- **Knowledge base** — a named collection (topic/project) that scopes browsing, digests, and Gulp sessions. A Source may belong to several.

Cross-cutting: every knowledge-bearing object carries a **mastery state** (§F7).

> **Naming discipline:** "Source" is the umbrella only; **Subscription** is the streaming *form* of Source, while **Feeds** is the *surface* that manages Subscriptions — so Feeds is not a spine object (§4.1), just a place. The thing you usually point at is a **Snapshot**.

### 4.3 Navigation

Navigation is organized by **intent**, not by object type. The forms of Source and the derived objects live *inside* these surfaces (mostly as filters), so the rich model never turns into a wall of tabs.

**Mobile — bottom tab bar (4):**
`Today · Library · ⊕ Capture · You`
- `⊕ Capture` is the center action (sheet, not a tab); it produces a **Snapshot**.
- **Mobile is the consumption end** — capture, Gulp, conversation. There is no Inbox/triage tab; bulk triage and library/pack management live on web (below). So capture is never a black hole, `Today` carries a read-only **"recently captured / processing"** peek of what just landed.
- `Today` also surfaces the daily essentials: a persistent "**N due**" badge, the **Daily digest**, and — when captures finish processing — a lightweight **"N new to confirm"** batch-review card (the mobile form of review, §F2).
- Concepts, Conversations, and Knowledge bases are **filters inside Library**; feed management lives in `You/Settings`. Power is present, not in your face.

**Web — left sidebar (the power workspace):**
`Today · Inbox · Library · Feeds · Knowledge bases · Search · Settings`
- `Library` opens with **filter chips** — by form (Snapshots · Conversations), by derived type (Cards · Concepts), by Knowledge base, by mastery/`due` — instead of permanent sub-entries.
- A global `⌘K` command bar handles search + capture + jump-to.
- The workspace is three-pane where useful: list ▸ reader ▸ knowledge-pack/chat panel.

---

## 5. Key flows

Each flow: **trigger → steps → key screens → states → edge cases**, with mobile/web differences inline.

### F1 — Capture (intake)
**Goal:** get anything into Gulp in one gesture; never block on processing.

**Triggers:** share sheet / WeChat forward (mobile), email-in, in-app `⊕ Capture`, paste-a-link (web), manual note, screenshot, audio memo.

**Steps:**
1. User invokes capture from anywhere.
2. Gulp shows a **Capture confirm** (lightweight): detected title/type, target knowledge base (default: Inbox), optional one-line note, optional tags.
3. User confirms (or it auto-confirms after a short timeout for true one-gesture capture).
4. A **Snapshot** appears immediately in **Inbox** with status `Processing`.
5. Pack generation runs async (§F2); on completion it flips to `Ready` and (if enabled) fires a notification.

**Key screens:** Capture confirm sheet · Inbox list.

**States:** `Queued (offline)` → `Processing` → `Ready (awaiting review)` → `In library` (committed; or auto-committed when **auto-approve** is on, §F2) · `Needs attention` (extraction failed, §10.2).

**Mobile vs web:** mobile = OS share sheet → confirm sheet, then a "saved" toast and the item appears in `Today`'s recent-captures peek (no Inbox tab on mobile); web = `⌘K → paste`, lands in the `Inbox` surface. Both write the same Inbox state.

**Edge cases:** duplicate URL → offer "open existing" instead of re-capturing; paywalled/blocked page → capture whatever selection/text is available; unsupported file type → store as a Snapshot with no pack and flag it.

---

### F2 — Knowledge pack generation & review
**Goal:** turn a Snapshot into a structured, skimmable pack, then commit it (and its Cards) into the library — reviewed by default, but never as a hard blocker.

**Steps:**
1. Snapshot enters `Processing`; Gulp builds the **Knowledge pack**: summary → background → key terms → people/orgs → core claims → counter-views → connections to existing Concepts.
2. Candidate **Cards** are drafted from the pack (not yet scheduled).
3. On `Ready`, the Snapshot is `awaiting review` (unless auto-approve, below).
4. User reviews (see **Review model**): edit/dismiss pack elements, promote/reject draft Cards.
5. Commit — "**Add to library**" / "**Approve**" — moves the Snapshot, its accepted Cards, and new Concepts into the knowledge graph (Cards enter scheduling at §F7).

**Review model (default on, batchable, skippable):**
- **Default = required.** Captures sit `awaiting review` until approved, so nothing enters scheduling unvetted.
- **Batch.** Approve many at once — "approve all from these N captures" — not one Snapshot at a time.
- **Auto-approve (opt-in).** A setting — global, with a per-Feed/source override (§F6) — that commits packs+Cards automatically on `Ready`, skipping the gate. The path for mobile-only users who don't want to curate.
- **Two shapes, mapped to the two surfaces:**
  - *Lightweight batch review = a consumption act → available on mobile.* Surfaces as the "**N new to confirm**" card in `Today`: approve-all, or tap through a quick accept/reject strip.
  - *Deep curation = a management act → web only.* Full Snapshot detail (edit pack elements, split/merge Concepts, re-file into KBs) lives in the web `Inbox`/`Library`.

**Key screens:** `Today` batch-confirm card (mobile) · Snapshot detail (reader on one side, pack on the other; web) · draft-cards review strip.

**States:** Snapshot = `awaiting review` → `in library` (committed) / auto-committed (auto-approve); pack element = `suggested` → `kept` / `dismissed`; Card = `draft` → `accepted` (enters queue) / `rejected`.

**Mobile vs web:** web shows reader + pack side-by-side (three-pane) for deep curation; mobile does lightweight batch-confirm from `Today`, and can open a single Snapshot in a stacked segmented control (`Read · Pack · Cards`) for a quick look — but bulk triage and management stay on web.

**Edge cases:** thin/low-confidence content → pack shows only what's reliable and says so; very long content (book/long video) → pack is section-chunked with per-section cards; **mobile-only user** → closes the loop via the `Today` batch-confirm (or auto-approve), never needing web (§F8).

---

### F3 — Library & knowledge base browsing
**Goal:** find, relate, and act on what you've gulped; make mastery legible.

**Steps / entries:** browse by object type, by knowledge base, by Concept, or via global search. Open any object → see its connections (related Concepts, Sources, Cards) → act (start a focused Gulp session, open a Conversation, edit).

**Key screens:** Library list (filter by form / type / KB / mastery state / due) · Concept page (definition, mastery state, linked everything, "test me on this") · Knowledge-base home (overview + its digest + "Gulp this base").

**States shown per item:** mastery state (§7), `due` indicator, last-reviewed, source freshness.

**Mobile vs web:** web = dense, multi-column, graph/connections panel; mobile = single-column list with filter chips and a Concept page optimized for quick read + "test me."

**Edge cases:** empty library → onboarding nudge to capture first item; huge library → search-first, with saved filters.

---

### F4 — Gulp mode (the daily learning session) — hero flow
**Goal:** in 5–10 minutes, advance mastery: learn new, review due, repair misses.

**Trigger:** `Today` screen "Start Gulp" (or notification deep-link, or "Gulp this base/Concept" for a scoped session).

**Session composition (auto-built):** today's new knowledge + due reviews + retests of recent misses, interleaved; session length adapts to the user's chosen duration (default 5 min).

**Steps (per item, one-at-a-time, full-bleed):**
1. Prompt shown — type varies: short-answer, multiple-choice, explain-it, apply-it, cloze, or "say it in your own words."
2. User responds (tap option / type / speak).
3. Reveal answer + the source-grounded explanation; for free responses, AI gives brief feedback.
4. User self-grades where needed (`Got it / Fuzzy / Missed`) — this feeds scheduling (§F7).
5. Inline affordances: "**Explain more**" (opens a mini conversation, §F5), "**Why am I seeing this?**", "**Snooze**".
6. Advance to next.
7. **Session summary:** items reviewed, new mastered, still-fuzzy, streak, "what to gulp next."

**Key screens:** Today (pre-session) · Card prompt · Reveal/feedback · Session summary.

**States:** session = `building` → `active` → `complete` / `abandoned (resumable)`; per-item grade feeds the scheduler.

**Mobile vs web:** identical interaction model; mobile is thumb-zone first (answers reachable bottom), web supports keyboard (1–4 to answer, space to reveal, enter to continue). Both support a "quick 5" and "keep going."

**Edge cases:** nothing due + nothing new → offer a "free explore" or "review at-risk" session, never a dead end; mid-session network loss → continue locally, sync grades later; interruption → resume exactly where left off.

---

### F5 — Conversation capture (chat → knowledge)
**Goal:** let the user interrogate any object, and never lose what they learned.

> A **Conversation** is itself a form of Source (§4.2) — an interactive one — so everything it yields lands in the same library as a captured Snapshot.

**Trigger:** "Discuss" on any Source/Concept/Card, "Explain more" inside Gulp mode, or a free chat in a knowledge base.

**Steps:**
1. Open a **Conversation** anchored to the object; context (the Snapshot/pack/Concept) is loaded and cited.
2. User asks; answers cite the underlying Source(s); user can follow up.
3. On exit (or "Save what I learned"), Gulp proposes a **sediment sheet**: new points, corrected misconceptions, candidate new Cards, Concepts touched, and "questions to review."
4. User accepts items → they enter the library and scheduling; the Conversation itself is saved as a reviewable Source.

**Key screens:** Conversation thread (with citation chips) · Sediment review sheet.

**States:** Conversation = `active` → `saved` (with sediment) / `discarded`; proposed items = `suggested` → `kept`/`dismissed`.

**Mobile vs web:** web = chat panel beside the reader; mobile = full-screen chat with a "context" peek. Sediment sheet identical.

**Edge cases:** long conversation → sediment summarizes thematically; user discards → still keep the thread (no silent data loss), just create no Cards.

---

### F6 — Feeds (subscriptions) & digests
**Goal:** turn followed feeds into a personalized, digestible stream — not an infinite inbox.

**Steps:**
1. Add a **Subscription** (RSS / newsletter address / channel) or import OPML.
2. New items auto-create **Snapshots** (lightweight, unprocessed) under that subscription.
3. Gulp assembles a **Daily digest** (and a **Weekly review**): "what's worth your time, why, and how it connects to what you already know," not a raw feed dump.
4. From the digest, the user can: read, gulp (full pack), dismiss, or send straight into a Gulp session. A per-Subscription **auto-approve** (§F2) lets trusted feeds skip the review gate, while ad-hoc captures still require review.

**Key screens:** Feeds list (per-subscription health, unread count, mute, **auto-approve toggle**) · Daily digest (ranked, reasoned cards) · Weekly review (themes, concept evolution, "saved but not yet mastered").

**States:** subscription = `active`/`muted`/`error`; digest item = `unseen`/`read`/`gulped`/`dismissed`.

**Mobile vs web:** digest is mobile-primary (lives in `Today` as a daily card stack); feed management is web-primary (the `Feeds` surface).

**Edge cases:** noisy feed → per-subscription filters and a "too much from here" control; feed fetch error → surfaced on Feeds, never blocks the digest.

---

### F7 — Mastery & review scheduling
**Goal:** make "do I actually know this?" a tracked, evolving state, and surface the right items at the right time.

**Model (v1, simple):** each Card carries a scheduling state. Grades from Gulp mode (`Got it / Fuzzy / Missed`) adjust the next-review interval (lengthen on success, reset/shorten on miss). Architecture leaves room to swap in FSRS later without changing the interaction.

**Mastery — 3 states by default, full ladder underneath.** Day-to-day UI shows three states — `New → Learning → Known` — plus the side-state `Due`. The fine-grained ladder (`Unread → Read → Summarized → Can recall → Can distinguish → Can apply → Mastered`, plus `At risk of forgetting`) is kept in the model and surfaced on the Concept/Card detail and stats. So power users get the granularity; the daily UI never carries seven badges.

**Where it surfaces:** `Today` due count; per-item badges in Library (the 3-state view); Concept page progress (full ladder); Weekly review's "at risk" list.

**Edge cases:** import spike (many cards due at once) → scheduler caps daily load and spreads the backlog; long absence → "ease back in" session prioritizing at-risk over new.

---

### F8 — Onboarding (first capture → first gulp)
**Goal:** reach the aha — "I forwarded something and got tested on it" — as fast as possible.

**Steps:**
1. Minimal sign-in.
2. **Pick interests / paste 1–3 things you follow** (seeds first Concepts/Subscriptions) — skippable.
3. **Install capture** where it matters: share sheet hint (mobile) / `⌘K` + email-in (web). Guided "capture your first thing now."
4. First Snapshot processes → first **knowledge pack** revealed with a one-line tour.
5. **First Gulp mini-session** (2–3 cards) → session summary celebrates the loop and sets the daily reminder.

**Key screens:** sign-in · interest/seed · capture-setup · first-pack tour · first mini-session.

**Edge cases:** user skips capture setup → still seed a sample Snapshot so they can experience a pack + mini-session immediately; **mobile-only user** → the first pack's Cards are confirmed via the `Today` batch-confirm card (or onboarding offers auto-approve), so the loop closes without ever touching web (§F2).

---

### F9 — Notifications & re-engagement
**Goal:** bring the user back to the daily loop without nagging.

- **Daily Gulp reminder** (user-set time) → deep-links into a ready session.
- **"Pack ready"** (optional, batched) when a capture finishes processing.
- **"At risk"** nudge when high-value concepts approach forgetting.
- **Weekly review** prompt.

**Rules:** all opt-in and rate-limited; every notification deep-links to a single next action; a "quiet" mode and per-type toggles in `You/Settings`.

---

## 6. Key-screen inventory

| Screen | Surface | Primary job | Primary action |
|---|---|---|---|
| Today | both | "what to do now" (+ mobile batch-confirm of new captures) | Start Gulp / Approve new |
| Capture confirm | both | one-gesture save | Confirm |
| Inbox | web-led | triage recent captures (mobile triages via `Today`) | Open / approve |
| Snapshot detail | both | read + curate pack (deep curation web-only) | Add to library |
| Library list | both | find & filter | Open object |
| Concept page | both | understand + test | Test me |
| Gulp prompt / reveal | both | learn one thing | Answer → grade |
| Session summary | both | close the loop | Continue / done |
| Conversation | both | interrogate + sediment | Save what I learned |
| Daily digest | both | curated stream (in Today on mobile) | Read / gulp |
| Feeds | web-led | manage subscriptions | Add / mute |
| Weekly review | both | see evolution | Gulp at-risk |
| Settings / You | both | preferences, notifications | — |

---

## 7. Cross-cutting states

Every list and object screen defines these explicitly:

- **Loading** — skeletons, never spinners-on-blank; lists stay interactive as items stream in.
- **Empty** — purposeful empty states that point to the next action (capture, subscribe, start onboarding).
- **Processing** — async pack generation; item visible and openable (shows what's ready) while the rest fills in.
- **Error / failed extraction** — item kept as a Snapshot with a "couldn't fully read this" banner + retry + "open original."
- **Offline** — capture queues; reads from cache; Gulp mode runs on locally-cached due items; a subtle offline indicator; sync on reconnect.
- **Limit / quota** (if applicable) — soft-degrade (queue rather than block) and explain.

---

## 8. Cross-device continuity

- A session started on web is resumable on mobile and vice-versa (same `active`/`abandoned` session state).
- Capture on any surface appears on all within sync latency.
- "Continue where you left off" surfaces on `Today` for an interrupted Snapshot read or Gulp session.

---

## 9. Accessibility & input

- Full keyboard control on web (Gulp answers `1–4`, reveal `space`, next `enter`, capture `⌘K`).
- Mobile: thumb-reachable primary actions; voice input for "say it in your own words"; haptics on grade.
- Respect dynamic type / reduced motion; all interactive targets ≥ 44px; sufficient contrast (defer exact tokens to design system).

---

## 10. Edge cases & failure handling (consolidated)

1. **Duplicate capture** → dedupe by URL/hash; offer the existing Snapshot.
2. **Extraction failure** → keep the Snapshot, flag `Needs attention`, retry + open-original.
3. **Unsupported content** → store raw, no pack, clearly labeled; still taggable/searchable.
4. **Offline** → queue captures, cache reads, run Gulp on cached items, sync later.
5. **Empty session** → never dead-end; offer at-risk review or free explore.
6. **Backlog spike** → scheduler caps daily due load and spreads overflow.
7. **Conversation discard** → keep the thread, create nothing; no silent loss.
8. **Sync conflict** → last-write-wins on scalars, union on collections.

---

## 11. Out of scope (v1) / open questions

**Deferred:** browser extension (one-click web capture), team/shared knowledge bases, public sharing/publishing, content marketplace, advanced graph visualization, FSRS (interaction is FSRS-ready; algorithm swap is later), full localization beyond zh/en.

**Decided (was open):** review of AI-drafted packs/Cards is **required by default**, **batchable**, and **skippable via auto-approve** (global + per-Feed override). Review has two shapes — lightweight batch-confirm (consumption, on mobile in `Today`) and deep curation (management, web only). See §F2.

**Open questions:**
- Default Gulp session length and whether it auto-adapts to available time.
- Digest cadence/volume defaults per user.
- Whether a `Snapshot` always stores its full content body or keeps only the reference/link (storage cost vs. link-rot protection).
- Web `Inbox`: keep it as a pinned sidebar entry, or fold it into Library as a "new / unprocessed" filter?

---

*Next docs in this set (proposed): `02-data-model.md`, `03-information-architecture.md` (detailed), `04-gulp-mode-detailed.md` (component-level).*
