# 02 — Data Model

*Gulp · logical data model · v1 · 2026-06-23*

> Companion to [`00-product-one-pager.md`](00-product-one-pager.md) (the *what/why*) and [`01-interaction-spec.md`](01-interaction-spec.md) (the *how the user moves through it*). This doc defines **the objects the product is made of** — their fields, states, relationships, and the rules that must always hold.
>
> **Altitude:** logical / domain model. It is technology-agnostic — entities, logical types, lifecycle states, cardinality, and invariants — **not** a physical schema. No SQL, no chosen datastore, no indexes. The concrete data/API contract (DDL, types, sync protocol) is a later doc; `01 §11` flagged it as such, and this doc is the bridge to it.
>
> Where `01` left a data-model question open (`01 §11`), this doc **resolves it with a decision** and marks whether the decision is reversible (§8).

---

## 1. Scope & reading guide

- **Covers:** every object named in `01 §4.2` (the spine) plus the operational objects the flows in `01 §5` require (sessions, review events, digests, sediment). One subsection per entity in §4.
- **Faithful to `01`, not `00`.** `00 §MVP` listed a longer object set (`Source · Claim · Concept · Question · Card · Conversation · Insight`); `01 §4.2` deliberately pruned it — *Claim* and *Question* are folded into the knowledge pack and Cards, *Insight* is "just a free-form Card." This doc follows the pruned `01` set.
- **The spine drives the layout.** Read every entity through the one-line model from `01 §4.1`:
  > You **save** things → Gulp **digests** them → turns them into **practice** → tracks what you **master** → and lets you **organize** it.
- **Out of scope:** physical storage, query/index design, API shapes, auth, the realtime sync wire protocol (only its *effect* on fields is modeled, §2.3). Anything in `01 §11` "Deferred" stays deferred here (§9).

---

## 2. Modeling conventions

### 2.1 Type legend

| Notation | Meaning |
|---|---|
| `ID` | opaque unique identifier |
| `string` / `text` | short / long free text |
| `enum{a·b·c}` | closed set of values |
| `bool` `int` `float` | scalars |
| `timestamp` | instant (UTC) |
| `X?` | nullable / optional |
| `X[]` | ordered or set-valued collection of `X` |
| `→Entity` | reference to another entity (by `ID`) |
| *value object* | a structured value owned inline by its parent, not independently addressable |

### 2.2 Fields implicit on every entity

To avoid repetition, every entity below **also** carries these and they are omitted from the per-entity tables:

| Field | Type | Notes |
|---|---|---|
| `id` | `ID` | stable, globally unique |
| `owner` | `→User` | single owner in v1 (no sharing — `01 §1`) |
| `created_at` | `timestamp` | |
| `updated_at` | `timestamp` | drives sync conflict resolution (§2.3) |
| `deleted_at` | `timestamp?` | **soft delete**; rows are tombstoned, never hard-deleted, so sync and "no silent data loss" (`01 §10.7`) hold |

### 2.3 Sync-shaped fields

`01 §3` defines the sync rule; the data model honors it structurally rather than with a protocol:

- **Scalars** resolve **last-write-wins** by `updated_at`. No per-field vector clocks in v1.
- **Collections** (e.g. `tags`, knowledge-base memberships, concept links) resolve by **union**. They are therefore modeled as sets / join entities, never as a single scalar blob that one writer could clobber.
- **Offline capture** is just a normal entity created locally with status `queued`; it uploads on reconnect (`01 §10.4`). No special "draft" type.

### 2.4 Derived vs. stored

Some values are **never stored** — they are computed on read so they can't drift out of sync (§9 invariant). They are listed in entity tables tagged *(derived)*. The two big ones: the daily 3-state mastery view and the `due` flag (both derived from `MasteryState` + `SchedulingState`, §5), and the **Inbox** (a derived view over `Snapshot`, §8).

---

## 3. The model at a glance

The entity set, grouped by the spine step it serves:

| Spine step | Entities |
|---|---|
| **Save** | `Source` → `Snapshot` · `Conversation` · `Subscription` |
| **Digest** | `KnowledgePack` (abstract; per-`pack_type` impls, e.g. `PaperPack` + `PackSection` / `PackBlock`) |
| **Practice** | `Card`, `GulpSession`, `ReviewEvent` |
| **Master** | `MasteryState` (vo), `SchedulingState` (vo), `Concept`, `ConceptEdge` |
| **Organize** | `KnowledgeBase`, `Digest` / `DigestItem` |
| **(account)** | `User` |
| **(capture-from-chat)** | `ConversationMessage`, `Sediment` / `SedimentItem` |

```mermaid
erDiagram
    User ||--o{ Source : owns
    Source ||--o| KnowledgePack : "snapshot has"
    KnowledgePack ||--o{ PackSection : "paper report body (PaperPack)"
    Source ||--o{ Card : "drafted from"
    Card }o--o{ Concept : "tests (link)"
    Source }o--o{ Concept : "about (link)"
    Concept ||--o{ ConceptEdge : "graph edge"
    KnowledgeBase }o--o{ Source : "membership"
    Source ||--o{ ConversationMessage : "conversation has"
    Source ||--o| Sediment : "conversation yields"
    Sediment ||--o{ SedimentItem : proposes
    Source ||--o{ Source : "subscription emits snapshot"
    Source ||--o{ FeedEntry : "subscription fetches"
    GulpSession }o--o{ Card : composition
    GulpSession ||--o{ ReviewEvent : logs
    Card ||--o{ ReviewEvent : graded-by
    Digest ||--o{ DigestItem : ranks
```

> `Snapshot`, `Conversation`, and `Subscription` are the three **forms of `Source`** (one entity, `kind` discriminator — §4.2). The diagram draws them as `Source` to keep the umbrella visible; the self-reference *"subscription emits snapshot"* is one `Source` row pointing at another.

---

## 4. Core entities

### 4.1 `User`

The account. Holds the few settings the flows reference; everything else hangs off it via `owner`.

| Field | Type | Notes |
|---|---|---|
| `display_name` | `string?` | |
| `locale` | `enum{zh·en}` | v1 languages (`01 §11`) |
| `auto_approve_default` | `bool` | *(parked with the snapshot gate — `01 §F2` amendment 2026-07-02; re-enters with auto-process/feeds)* |
| `gulp_session_minutes` | `int` | default session length (default 5; `01 §F4`) |
| `daily_reminder_at` | `string?` | local time-of-day for the Gulp reminder (`01 §F9`) |
| `notification_prefs` | *value object* | per-type opt-in + quiet mode (`01 §F9`) |

> Notification *delivery* is ephemeral and not modeled as a stored entity in v1 — only the **preferences** above are durable. Each notification deep-links to one next action at send time.

---

### 4.2 `Source`

`Source` is abstract — you never store a bare Source, only one of three **forms**, distinguished by `kind`. One entity, one discriminator, form-specific fields nullable when not applicable (the *single-table-with-`kind`* decision, §8). This mirrors `01 §4.2` directly: *"Source is the umbrella; you create one of its three forms."*

**Shared fields (all forms):**

| Field | Type | Notes |
|---|---|---|
| `kind` | `enum{snapshot·conversation·subscription}` | the discriminator |
| `title` | `string` | detected at capture or user-set |
| `note` | `text?` | optional one-line note from capture (`01 §F1`) |
| `tags` | `string[]` | union-on-conflict (§2.3) |
| `status` | `enum` | **domain depends on `kind`** — see the form below and the consolidated state machines (§6) |

The form-specific fields follow in §4.3–4.5. Knowledge-base membership is a join, not a field (§4.9).

> **Mastery on a Source is *derived*, not stored.** A Source has no `MasteryState` of its own; its mastery is a rollup of its Cards' states (§5.1). Only `Card` and `Concept` store mastery.

---

### 4.3 `Snapshot` (`kind = snapshot`)

The frozen, point-in-time item — "the everyday thing you gulped" (`01 §4.2`). Fields present when `kind = snapshot`:

| Field | Type | Notes |
|---|---|---|
| `media_type` | `enum{article·pdf·video·podcast·note·screenshot·audio·webpage}` | the **media format** — how the bytes arrived |
| `genre` | `enum{paper·article·note·…}?` | the **knowledge genre** — what kind of knowledge artifact this is; detected at parse time by heuristics, user-correctable, selects the pack-production strategy (§4.4). Null until first processed. Open / extensible. |
| `origin_url` | `string?` | original reference (null for manual note / screenshot / audio memo) |
| `content_body` | `text?` | **stored extracted content** — the link-rot-proof copy (§8 decision) |
| `content_ref` | `string?` | pointer to the stored original/blob (media, raw file) |
| `captured_via` | `enum{share_sheet·wechat·email·in_app·paste·manual·screenshot·audio_memo·feed}` | provenance (`01 §F1`; `feed` = promoted from a subscription, spec 2026-07-09) |
| `emitted_by` | `→Source?` | the `Subscription` that produced it; null for ad-hoc captures (`01 §F6`) — **live** as of spec 2026-07-09 (was deferred with S7) |
| `pack` | `→KnowledgePack?` | 1–1; null until generated, and null forever for unsupported content (`01 §10.3`) |

**`status` domain (the capture lifecycle, `01 §F1`/`§F2` — amended 2026-07-02, single gate; see [`superpowers/specs/2026-07-02-single-gate-lifecycle-design.md`](superpowers/specs/2026-07-02-single-gate-lifecycle-design.md)):**
`unprocessed` → `processing` → `ready`, with `queued` (offline buffer), `exported` (job exported, awaiting result upload), and the branch `needs_attention` (extraction failed). Processing is **manually triggered** in v1 (S2 design §2.4). **`ready` is "in the library"** — the review states (`awaiting_review` / `in_library`) are parked with the snapshot-level gate; the only review gate is per-card `draft → accepted/rejected` (§4.5). Full transitions in §6.

---

### 4.4 `KnowledgePack` (abstract) + its per-type implementations

The AI-generated **digest** of a `Snapshot` — "what I understood after reading this." Exists **only** for a `Snapshot` (invariant, §9). `KnowledgePack` is a **thin abstract type**: it says only that a digest exists, names its content type, and guarantees it can be rendered. **The concrete shape is owned by a per-`pack_type` implementation** — a paper is digested very differently from a WeChat article or an X post, so the model does not force one shape on all of them.

**`KnowledgePack`** — the abstract base; every type shares exactly these:

| Field | Type | Notes |
|---|---|---|
| `snapshot` | `→Source` | the `kind=snapshot` it digests (1–1) |
| `title` | `text` | |
| `summary` | `text?` | one-paragraph gist — the skim / search / library-card entry; universal |
| `pack_type` | `enum{paper·article·…}` | discriminator selecting the implementation; open / extensible |
| `extras` | `json` | the per-`pack_type` additions (implemented 2026-07-09): `PaperPack` keeps `key_insight` / `core_contributions` / `references` here; `ArticlePack` leaves it empty. A new pack_type adds its fields here without a schema change. |
| `status` | `enum{generating·ready}` | |

Plus one behavioral contract every implementation satisfies:

- **`render()` → readable content** (Markdown / a common block list). Every consumer — the web reader, card generation, search, curriculum — goes through `render()`, so nothing downstream dispatches on `pack_type`. (The reader's *header* is the one exception: it projects `extras` per type.)

**Production is strategy-dispatched on `Source.genre`** (§4.3): `paper → PaperPack` via the LLM deep-read; `article`/`note`/anything unknown `→ ArticlePack` via the deterministic preserve transform. The fallback is always preserve — the worst case is "no enrichment", never a misrepresenting rewrite.

**Per-type implementations** own their structured content and implement `render()`:

**`PaperPack` (`pack_type = paper`)** — the deep, LLM-re-authored **paper report**: `extras = {key_insight, core_contributions[] (1–5), references[] ({citation, why_interesting})}`, plus the sectioned body below.

**`ArticlePack` (`pack_type = article`)** — the **preserved original** (implemented 2026-07-09): the source's own markdown deterministically re-shaped into the sectioned body — headings → sections; fenced code → `code` blocks; pipe tables → `table`; standalone images → `figure` (with remote `url`); `$$…$$` → `formula`; everything else verbatim `prose`. **Zero LLM in the pack path**; `summary` comes from the page's meta description or the first paragraph. This is the digest for content that is already well-authored (technical blogs, notes) — Gulp adds structure and learning machinery, not a rewrite.

**`PackSection` / `PackBlock`** — the **shared readable body of every pack type** (not `PaperPack`'s private shape): ordered sections of ordered, typed blocks. Block editing, per-block chat, and figure linking all attach here, so every pack type gets them for free.

| `PackSection` field | Type | Notes |
|---|---|---|
| `pack` | `→KnowledgePack` | parent |
| `heading` | `string?` | null = an unlabelled lead-in section (e.g. an article's intro) |
| `position` | `int` | order within the pack |

| `PackBlock` field | Type | Notes |
|---|---|---|
| `section` | `→PackSection` | parent |
| `block_type` | `enum{prose·formula·table·figure·list·code}` | |
| `data` | `json` | the variant fields per type (below) |
| `position` | `int` | order within the section |

| `block_type` | `data` shape | Use |
|---|---|---|
| `prose` | `{content}` | Markdown; `**bold**`, inline `$math$` |
| `formula` | `{latex, explanation}` | display equation + one-line explanation |
| `table` | `{headers, rows, caption?}` | results / baseline comparisons |
| `figure` | `{label, explanation, figure_id?, url?}` | `figure_id` → a stored `SourceFigure` asset; `url` → the original remote image (article packs); neither → described in words |
| `list` | `{items, ordered?}` | hyperparameters, sub-points |
| `code` | `{language?, content}` | verbatim code blocks (essential for technical articles) |

**`PackBlockMessage`** — the per-block conversation (the web reader's "Discuss" panel; the S6 anchor made concrete).

| Field | Type | Notes |
|---|---|---|
| `block` | `→PackBlock` | cascade-deletes with the block |
| `role` | `enum{user·assistant}` | |
| `content` | `text` | grounded on the block + section + pack + source body |

> **Extensible by design.** A new content type = a new `genre` value + a strategy that fills `extras` and the shared body; the abstract base, the reader's entry point, card generation, and search do not change. Adding `XiaohongshuPack` / `XPostPack` touches only its own strategy.
>
> **Every pack is a living document:** blocks are editable in place, and can be added / deleted / reordered in the web reader (block ids are stable API objects). **Re-running processing replaces the pack wholesale** — manual edits and block chats are discarded (confirmed in the UI). There is **no facet layer** — Cards are generated *from* the pack's rendered content (plus the reader's conversation) on demand (§4.5, cards spec; `01 §F2`), not from an intermediate facet model.

### 4.5 `Card`

The atomic, testable unit — "the unit of Gulp mode and scheduling" (`01 §4.2`). A **user takeaway is just a `Card` with `origin = user`** — there is no separate *Insight* entity.

| Field | Type | Notes |
|---|---|---|
| `source` | `→Source?` | what it was drafted from (null allowed for a standalone takeaway) |
| `card_type` | `enum{flashcard·mcq·cloze}` | interaction contract: `flashcard` = front→flip→self-grade · `mcq` = pick one · `cloze` = fill a blank (`01 §F4`) |
| `prompt` | `text` | |
| `answer` | `text?` | canonical answer or rubric for AI feedback |
| `explanation` | `text?` | source-grounded reveal explanation (`01 §F4`; S2 design §4) |
| `options` | `string[]?` | choices for `mcq` |
| `origin` | `enum{pack·conversation·user}` | drafted from a pack, sedimented from a conversation, or hand-authored |
| `status` | `enum{draft·accepted·rejected}` | enters scheduling only at `accepted` (invariant, §9) |
| `scheduling` | `SchedulingState` (vo) | §5.2 — meaningful only once `accepted` |
| `mastery` | `MasteryState` (vo) | §5.1 |

Concept attachments are a join, not a field (§4.6).

---

### 4.6 `Concept` + `ConceptEdge`

The normalized idea/term/person/org and the edges between them — "the spine of the knowledge graph" (`01 §4.2`).

**`Concept`**

| Field | Type | Notes |
|---|---|---|
| `concept_type` | `enum{idea·term·person·org}` | *people/orgs from a pack are Concepts of this subtype* — not a separate entity |
| `name` | `string` | normalized canonical name |
| `aliases` | `string[]?` | merge targets / surface forms |
| `definition` | `text?` | |
| `mastery` | `MasteryState` (vo) | aggregate rollup over linked Cards; stored denormalized for the Concept page (`01 §F3`) |

**`ConceptEdge`** — typed, directed edge; the graph is `Concept`-to-`Concept` many-to-many via this entity.

| Field | Type | Notes |
|---|---|---|
| `from_concept` | `→Concept` | |
| `to_concept` | `→Concept` | |
| `relation` | `enum{related·part_of·contrasts·causes·example_of}` | extensible |
| `weight` | `float?` | connection strength |

**Typed links** (each a join entity so they union under sync, §2.3):

| Link | From → To | Carries |
|---|---|---|
| `CardConcept` | `Card → Concept` | `role?` (what the Card tests about the Concept) |
| `SourceConcept` | `Source → Concept` | `role?` (`mentions` / `about`) |

---

### 4.7 `Conversation` (`kind = conversation`) + messages + sediment

A Conversation is itself a **form of `Source`** (`01 §F5`) — an interactive one — so what it yields lands in the same library. Fields present when `kind = conversation`:

| Field | Type | Notes |
|---|---|---|
| `anchor_type` | `enum{source·concept·card·knowledge_base·pack_block·none}` | what it's anchored to (`01 §F5`); `pack_block` = a block inside a pack report (S2 design §3) |
| `anchor_ref` | `ID?` | the anchored object (polymorphic; null when `anchor_type = none`) |
| `sediment` | `→Sediment?` | produced on save |

**`status` domain:** `active` → `saved` (with sediment) / `discarded`. Discard keeps the row and its messages — it just creates no Cards (no silent loss; `01 §10.7`, §9 invariant).

**`ConversationMessage`** (child entity, ordered)

| Field | Type | Notes |
|---|---|---|
| `conversation` | `→Source` | the `kind=conversation` parent |
| `role` | `enum{user·assistant}` | |
| `text` | `text` | |
| `citations` | `→Source[]` | the citation chips — Sources the answer grounds on (`01 §F5`) |

**`Sediment`** — the "save what I learned" proposal; a thin parent over its items.

| Field | Type | Notes |
|---|---|---|
| `conversation` | `→Source` | |

**`SedimentItem`** — carries the `suggested → kept/dismissed` review shape (per-item accept, like Cards).

| Field | Type | Notes |
|---|---|---|
| `sediment` | `→Sediment` | parent |
| `item_type` | `enum{new_point·corrected_misconception·candidate_card·concept_touched·question_to_review}` | `01 §F5` |
| `text` | `text?` | |
| `concept` | `→Concept?` | for `concept_touched` |
| `card` | `→Card?` | set when a `candidate_card`/`question_to_review` is `kept` and promoted |
| `state` | `enum{suggested·kept·dismissed}` | |

---

### 4.8 `Subscription` (`kind = subscription`) + `FeedEntry`

> **Amended 2026-07-09** (spec [`superpowers/specs/2026-07-09-subscription-system-design.md`](superpowers/specs/2026-07-09-subscription-system-design.md)): implemented as built. Items do **not** auto-create Snapshots; they land in a lightweight `FeedEntry` table and an explicit **gulp** promotes one. `feed_type`, `auto_approve` (parked with the snapshot gate), and the stored `status`/`unread_count` are dropped — health and unread are **derived**.

The streaming form of `Source` — a followed feed, RSSHub/Folo-compatible. Fields present when `kind = subscription`:

| Field | Type | Notes |
|---|---|---|
| `feed_url` | `string` | canonical address: `rsshub://ns/path` (instance-independent, Folo convention) or plain `https://…` RSS/Atom |
| `muted` | `bool` | "too much from here" control (`01 §F6`) — stops polling, keeps data |
| `last_fetch_at` | `timestamp?` | |
| `last_fetch_error` | `text?` | null = healthy; set/cleared per fetch |
| `feed_etag` / `feed_http_modified` | `string?` | conditional GET (HTTP 304) |
| `consecutive_failures` | `int?` | ≥5 → poll backs off to daily |

**Health is derived, not stored:** `muted` → `muted`; `last_fetch_error != null` → `error`; else `active`. `unread_count` is derived from `FeedEntry.read_at`. `Source.status` is constant `ready` for subscription rows.

**`FeedEntry`** — lightweight, prunable feed items (unpromoted entries older than 90 days are swept weekly):

| Field | Type | Notes |
|---|---|---|
| `subscription` | `→Source` | cascade-deleted with the subscription |
| `guid` | `string` | feed-provided id, else hash(link+title); **unique per subscription** (dedup) |
| `title` / `url` / `author` / `published_at` | | list display |
| `content_html` | `text?` | feed-provided content — powers the Feeds reading pane |
| `read_at` | `timestamp?` | null = unread |
| `promoted_source` | `→Source?` | set on gulp; doubles as the "already gulped" record |

> Promotion ("gulp") creates a `Source(kind=snapshot, captured_via=feed)` through the normal capture path and enqueues processing; the Snapshot points **back** at the Subscription via `Snapshot.emitted_by` (§4.3) — a `Source → Source` reference, not a separate join.

---

### 4.9 `KnowledgeBase` + membership

> **Parked (2026-07-02).** KB membership is source-level many-to-many — structurally a named tag — and `SourceTag` already exists, so v1 grouping/scoping uses **tags**. KB graduates back when tags prove insufficient (description, per-KB digest). See [`superpowers/specs/2026-07-02-single-gate-lifecycle-design.md`](superpowers/specs/2026-07-02-single-gate-lifecycle-design.md).

A named collection that scopes browsing, digests, and Gulp sessions (`01 §4.2`). A Source may belong to several → many-to-many.

**`KnowledgeBase`**

| Field | Type | Notes |
|---|---|---|
| `name` | `string` | |
| `description` | `text?` | |

**`KBMembership`** (join; union-on-conflict, §2.3)

| Field | Type | Notes |
|---|---|---|
| `knowledge_base` | `→KnowledgeBase` | |
| `source` | `→Source` | |

> **There is no "Inbox" entity.** Inbox is a derived view, not a stored KB (§8 decision). Deleting a KB tombstones the KB and its memberships — never the member Sources (§9 invariant).

---

### 4.10 `GulpSession` + `ReviewEvent`

The daily learning session (`01 §F4`) and the immutable grade log that feeds scheduling (`01 §F7`).

**`GulpSession`**

| Field | Type | Notes |
|---|---|---|
| `scope_type` | `enum{daily·knowledge_base·concept·free_explore·at_risk}` | how the session was launched (`01 §F4`) |
| `scope_ref` | `ID?` | the KB / Concept for a scoped session |
| `target_minutes` | `int` | from `User.gulp_session_minutes`, overridable per session |
| `composition` | `→Card[]` | the interleaved items: new + due + retests (`01 §F4`) |
| `status` | `enum{building·active·complete·abandoned}` | `abandoned` is **resumable** (`01 §F4`/`§8`) |
| `started_at` | `timestamp?` | |
| `completed_at` | `timestamp?` | |

The session summary (items reviewed, new mastered, still-fuzzy, streak) is **derived** from the session's `ReviewEvent`s, not stored.

**`ReviewEvent`** — append-only; one per graded item.

| Field | Type | Notes |
|---|---|---|
| `session` | `→GulpSession` | |
| `card` | `→Card` | |
| `grade` | `enum{got_it·fuzzy·missed}` | the self-grade (`01 §F4`/`§F7`) |
| `response` | `text?` | the user's free response, when captured |
| `at` | `timestamp` | |

> `ReviewEvent`s are the source of truth for review history. `Card.scheduling` is a **fold** over them (§9 invariant) — which is what keeps the FSRS swap (`01 §11`) a pure-algorithm change.

---

### 4.11 `Digest` + `DigestItem`

The curated stream (`01 §F6`): the Daily digest and Weekly review. A digest is an assembled, ranked selection — not a feed dump.

**`Digest`**

| Field | Type | Notes |
|---|---|---|
| `digest_type` | `enum{daily·weekly}` | daily digest vs. weekly review |
| `period` | `string` | the day/week it covers |

**`DigestItem`**

| Field | Type | Notes |
|---|---|---|
| `digest` | `→Digest` | |
| `ref_type` | `enum{snapshot·card·concept}` | what the item points at |
| `ref` | `ID` | the referenced object |
| `rank` | `int` | order in the stream |
| `reason` | `text` | "why it's worth your time / how it connects" (`01 §F6`) |
| `state` | `enum{unseen·read·gulped·dismissed}` | `01 §F6` |

---

## 5. Cross-cutting value objects

These are owned **inline** by their parents (not independently addressable) and appear on multiple entities.

### 5.1 `MasteryState`

`01 §F7` is explicit: **store the fine-grained ladder; surface three states.** So the ladder rung is the only stored field — the daily view and `due`/`at_risk` are derived.

| Field | Type | Notes |
|---|---|---|
| `ladder` | `enum{unread·read·summarized·can_recall·can_distinguish·can_apply·mastered}` | **stored** — the 7-rung ladder (`01 §F7`) |
| `daily` | *(derived)* `enum{new·learning·known}` | the 3-state day-to-day view |
| `due` | *(derived)* `bool` | `true` when `SchedulingState.next_review_at ≤ now` |
| `at_risk` | *(derived)* `bool` | approaching forgetting (drives "at risk" nudges & weekly list) |

**Ladder → daily mapping** (the derivation, single source of truth):

| `ladder` | `daily` |
|---|---|
| `unread`, `read` | `new` |
| `summarized`, `can_recall`, `can_distinguish` | `learning` |
| `can_apply`, `mastered` | `known` |

- Carried (stored) by **`Card`** and **`Concept`**.
- **`Source`** and **`KnowledgeBase`** mastery is a *rollup* of their Cards' states — derived, never stored (§4.2 note, §9 invariant).

### 5.2 `SchedulingState`

The per-`Card` review schedule. v1 is the simple interval model of `01 §F7`; the extra fields are reserved so FSRS drops in without an interaction change.

| Field | Type | Notes |
|---|---|---|
| `interval_days` | `float` | current spacing; lengthens on `got_it`, resets/shortens on `missed` |
| `ease` | `float` | difficulty multiplier (v1 simple model) |
| `next_review_at` | `timestamp` | drives `due` and session composition |
| `last_reviewed_at` | `timestamp?` | |
| `reps` | `int` | successful reviews |
| `lapses` | `int` | misses |
| `stability` | `float?` | **reserved for FSRS** (`01 §11`); unused in v1 |
| `difficulty` | `float?` | **reserved for FSRS**; unused in v1 |

> Meaningful only once `Card.status = accepted`. A `draft`/`rejected` Card carries an empty schedule (§9 invariant).

---

## 6. Lifecycle state machines (consolidated)

Every `status`/`state` field, in one place. (`Source.status` is split by form, since the discriminator selects the domain.)

| Entity · field | States | Transitions |
|---|---|---|
| **`Snapshot.status`** | `queued · unprocessed · processing · ready · exported · needs_attention` *(amended 2026-07-02 — single gate)* | capture lands `unprocessed`; processing is **manually triggered** (S2 §2.4): `unprocessed`→`processing`→`ready` (**= in library**); `unprocessed`→`exported`→`ready` (external job + import); `processing`→`needs_attention` (failed) → `processing` (retry); `queued` = offline buffer. The parked review states re-enter with unvetted inflow (auto-process / S7) |
| **`Conversation.status`** | `active · saved · discarded` | `active`→`saved` (with sediment) · `active`→`discarded` (keeps thread) |
| **`Subscription` health** *(derived, not stored — §4.8 amendment 2026-07-09)* | `active · muted · error` | `active`↔`muted` (muted flag) · `active`↔`error` (`last_fetch_error` set/cleared per fetch) |
| **`KnowledgePack.status`** | `generating · ready` | `generating`→`ready` |
| **`SedimentItem.state`** | `suggested · kept · dismissed` | `suggested`→`kept`/`dismissed` |
| **`Card.status`** | `draft · accepted · rejected` | `draft`→`accepted` (enters scheduling) / `rejected` |
| **`GulpSession.status`** | `building · active · complete · abandoned` | `building`→`active`→`complete`/`abandoned`; `abandoned`→`active` (resume) |
| **`DigestItem.state`** | `unseen · read · gulped · dismissed` | `unseen`→`read`/`gulped`/`dismissed` |

These realize the cross-cutting states in `01 §7` (Loading/Empty/Processing/Error/Offline are UI states over `processing`/`needs_attention`/`queued`).

---

## 7. Relationships & cardinality

| From | To | Cardinality | Via | Notes |
|---|---|---|---|---|
| `User` | `Source` | 1 — N | `owner` | owns everything |
| `Source(snapshot)` | `KnowledgePack` | 1 — 0..1 | `Snapshot.pack` | pack only for snapshots (abstract; a per-`pack_type` impl) |
| `PaperPack` | `PackSection` | 1 — N | `PackSection.pack` | the paper report spine (paper impl) |
| `PackSection` | `PackBlock` | 1 — N | `PackBlock.section` | ordered blocks |
| `PackBlock` | `PackBlockMessage` | 1 — N | `PackBlockMessage.block` | per-block conversation |
| `Source` | `Card` | 1 — N | `Card.source` | a Card may be sourceless (`user` takeaway) |
| `Card` | `Concept` | N — M | `CardConcept` | what a Card tests |
| `Source` | `Concept` | N — M | `SourceConcept` | what a Source is about |
| `Concept` | `Concept` | N — M | `ConceptEdge` | the knowledge graph |
| `KnowledgeBase` | `Source` | N — M | `KBMembership` | a Source in several KBs |
| `Source(conversation)` | `ConversationMessage` | 1 — N | `.conversation` | ordered thread |
| `Source(conversation)` | `Sediment` | 1 — 0..1 | `.sediment` | on save |
| `Sediment` | `SedimentItem` | 1 — N | `.sediment` | |
| `Source(subscription)` | `Source(snapshot)` | 1 — N | `Snapshot.emitted_by` | feed emits snapshots (via explicit gulp — §4.8) |
| `Source(subscription)` | `FeedEntry` | 1 — N | `.subscription` | fetched items; prunable working data |
| `GulpSession` | `Card` | N — M | `.composition` | interleaved items |
| `GulpSession` | `ReviewEvent` | 1 — N | `.session` | grade log |
| `Card` | `ReviewEvent` | 1 — N | `.card` | review history |
| `Digest` | `DigestItem` | 1 — N | `.digest` | |

---

## 8. Resolved decisions

Each resolves an open question from `01 §11` (or a modeling fork). **Reversible** = changeable later without reshaping consumers.

| # | Decision | Rationale | Reversible? |
|---|---|---|---|
| D1 | **Source = single entity + `kind` discriminator** (not three entities). | Matches `01 §4.2`'s framing 1:1; derived objects (`Card`, links, digest) reference one `Source` type instead of three. | Yes — could normalize into per-form tables behind the same references. |
| D2 | **Snapshot stores full extracted `content_body` *and* `origin_url`/`content_ref`.** | Link-rot protection is core to what a Snapshot *is* (`01 §4.2`). Resolves the `01 §11` open question. | **Yes** — `content_body` can move to a blob store via `content_ref` later; a physical concern (§9 deferred). |
| D3 | **Inbox is a derived view, not an entity.** Inbox = the pre-library funnel — a `Snapshot` not yet `ready` (`status ∈ {queued·unprocessed·processing·exported·needs_attention}`); `ready` = in the library (single gate, §6). | Resolves `01 §11`'s "pinned entry vs. filter" question — modeling it as a query means mobile (`Today` peek) and web (`Inbox`) are the same underlying set, no duplicated state. | Yes — UI may present it either way; the model doesn't care. |
| D4 | **Mastery stores the 7-rung ladder; the 3-state view and `due`/`at_risk` are derived.** | `01 §F7` explicitly wants both granularities without "seven badges" in daily UI. One stored source of truth → no drift. | Yes — mapping table (§5.1) is the only thing to change. |
| D5 | **No `Insight`/`Claim`/`Question` entities.** Takeaways are `Card(origin=user)`; claims/counter-views live in the report prose; questions are `Card`s. | Follows `01 §4.2`'s pruning of `00`'s longer list. | Yes — could promote any to a first-class entity later. |
| D6 | **`Card.scheduling` is a fold over append-only `ReviewEvent`s.** | Keeps history immutable and makes the FSRS swap (`01 §11`) a pure recompute, not a migration. | Yes. |
| D7 | **`KnowledgePack` is a thin abstract type + per-`pack_type` implementations** (§4.4); the readable, block-editable paper report is the `PaperPack` implementation, not the definition. There is **no facet layer**. v1 processing is **manual-trigger** (relaxes `01` principle 2) and reports are authored in English. | Digestion must span content types (paper · article · social post), so the base stays type-agnostic and each type owns its shape; reading-first digestion is the product thesis (`00`); manual trigger controls API cost. | Yes — new `pack_type`s slot in without touching the base (§4.4). |
| D8 | **Pack production dispatches on `Source.genre`, with the deterministic preserve strategy as the universal fallback** (2026-07-09, §4.3–4.4). `genre` (knowledge kind) is a separate axis from `media_type` (format), detected by pure heuristics at parse time and user-correctable; `paper` gets the LLM deep-read, `article`/`note`/unknown get the zero-LLM preserve transform into the shared block substrate. Per-type fields live in the base's `extras` json; the digest-export job applies to `genre=paper` only. | A well-authored technical article IS its own best pack — re-authoring it as a fake paper review destroys it; falling back to "preserve the original" guarantees every source gets appropriate (at worst neutral) processing, at zero AI cost; heuristics stay honest because misclassification is one visible, correctable field. | Yes — a genre is one strategy + enum value; swapping a genre's strategy (e.g. adding an LLM annotate pass for articles) touches only that strategy. |

---

## 9. Invariants

Rules that must always hold; they encode the product guarantees from `01`.

1. **A `KnowledgePack` exists only for a `Source` with `kind = snapshot`.** Conversations and Subscriptions never have packs.
2. **A `Card` participates in scheduling only when `status = accepted`.** `draft`/`rejected` Cards carry an empty `SchedulingState` and never surface as `due`. (`01 §F2`/`§F7`)
3. **Mastery is stored only as the ladder, only on `Card` and `Concept`.** Daily 3-state, `due`, `at_risk`, and Source/KB mastery are **always derived** — never persisted independently. (D4)
4. **Inbox is never stored.** It is the derived set in D3. Capturing "to Inbox" means *creating no `KBMembership`*, not joining an Inbox row.
5. **No silent data loss.** Discarding a `Conversation` sets `status = discarded` but keeps the thread and messages; it only forgoes Card creation. Soft delete (`deleted_at`) everywhere else. (`01 §10.7`)
6. **`ReviewEvent`s are append-only.** They are never edited or deleted; `Card.scheduling` is recomputed from them. (D6)
7. **Sync integrity.** Scalars resolve last-write-wins by `updated_at`; collection membership (`tags`, `KBMembership`, `CardConcept`, `SourceConcept`) resolves by union. No collection is stored as a clobberable scalar. (`01 §3`/`§10.8`, §2.3)
8. **Deleting a `KnowledgeBase` tombstones the KB and its memberships only** — never its member `Source`s.
9. **Unsupported / failed content is still a valid `Snapshot`** — with `pack = null` and `status = needs_attention` (failed) or `ready` (unsupported but shelved), still taggable and searchable. (`01 §10.2`/`§10.3`)

---

## 10. Deferred / open

Carried forward from `01 §11` or pushed to the physical-schema doc:

- **Physical storage of `content_body`** — inline vs. blob store (via `content_ref`). A schema concern, not a domain one (D2).
- **FSRS fields** — `stability`/`difficulty` are reserved (§5.2) but unused until the algorithm swap.
- **Ownership beyond a single user** — team/shared KBs, public sharing (`01 §11`); `owner` is single-valued in v1.
- **Localization** — only `locale ∈ {zh·en}`; no per-field translation model.
- **Realtime sync wire protocol** — only its field-level *effect* is modeled here (§2.3); the protocol itself is later.
- **Notification delivery records** — only preferences are stored in v1 (§4.1).

---

*Next docs in this set (proposed): `03-information-architecture.md` (detailed), `04-gulp-mode-detailed.md` (component-level), and the physical schema / API contract this model bridges to.*
