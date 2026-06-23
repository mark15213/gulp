# 03 — UI System

*Gulp · UI system / visual language · v1 · 2026-06-23*

> Companion to [`00-product-one-pager.md`](00-product-one-pager.md) and [`01-interaction-spec.md`](01-interaction-spec.md). The one-pager defines **what** Gulp is and **why**; the interaction spec defines **how the user moves through it**; this doc defines **how it looks and feels** — the visual language, design tokens, type, components, and the per-surface registers that dress the flows.
>
> **Altitude:** visual system + concrete tokens. It specifies the look, the named tokens, and component anatomy/states — not pixel-perfect comps (those come later) and not the data/API contract (that's `02-data-model.md`). Where mobile and web diverge, the difference is called out inline, exactly as in the interaction spec.
>
> **Scope of v1:** light theme only, English / Latin typography only. Dark theme and CJK pairing are deferred (§10), mirroring the interaction spec's deferral discipline.

---

## 1. Design approach — one spine, two registers

Gulp has two first-class clients with deliberately different jobs (interaction spec §3): the **mobile app is the consumption end** — capture, the daily Gulp habit, conversation — and the **web app is the management workbench** — deep reading, triage, library and feed work. Their ideal *feel* differs, so we don't force one look onto both. Instead:

**One spine, two registers.** A shared foundation guarantees "this is the same product"; two visual registers let each surface be excellent at its job.

| | **Web register** | **Mobile register** |
|---|---|---|
| **Reference feel** | Linear / Notion — precise, dense, systematic | Arc — characterful, warm, rewarding (sophisticated, *not* cartoon) |
| **Maps to spec role** | "the power workspace," management end | "the consumption end," daily ritual |
| **Color use** | near-grayscale + one functional blue accent | amplified blue brand + amber celebration |
| **Density** | high — multi-pane, compact rows | comfortable — single column, big tap targets |
| **Type** | small base (14px), tight, Inter-led | large base (16px), bigger jumps, Instrument Serif for hero moments |
| **Motion** | fast, functional, near-instant | expressive at moments of progress |
| **Input** | keyboard-first (`⌘K`, `1–4`, space, enter) | thumb-first, haptics, voice |

### 1.1 What the spine fixes (never diverges)

These read identically on both surfaces — they are the product's shared identity:

1. **Brand anchor — Gulp Blue** (§3.1). One blue, everywhere.
2. **Mastery-state color language** (§3.3). The five states are the product's core data language; a user moving between phone and laptop must never re-learn them.
3. **Type roles & tabular numerals** (§4). The same three families in the same roles; counts/intervals/streaks always set in mono.
4. **The Card as the atomic unit** and its shape language (§5.4). The data model *is* Cards; the UI's base element matches.
5. **The 4px spacing base and icon family** (§5.1, §2.6).
6. **Voice in microcopy** (§2.7) — plain, never clever-at-the-expense-of-clear.

### 1.2 Visual principles

The rules every screen obeys; when a visual decision is ambiguous, resolve toward these. They are the visual counterpart to the interaction spec's §2.

1. **State is always legible.** Every knowledge-bearing object shows its mastery state without a tap (interaction spec §2.3). Color + label, never color alone.
2. **Blue means "act."** The brand blue is rationed to the single most important action on a screen (and the `Due` state, which *is* a call to act). If everything is blue, nothing is.
3. **One thing in Gulp mode.** During a session the prompt is full-bleed with no competing chrome (interaction spec §2.6). The UI gets quieter, not louder, the more it matters.
4. **Celebration is mobile, and it's earned.** Amber, glow, and motion appear only at genuine moments of progress (streak, mastered, correct) — never on working surfaces, never on web's workbench.
5. **Density is a web feature, calm is a mobile feature.** Web earns its keep by showing more at once; mobile earns its keep by asking for one decision at a time.
6. **Skeletons, not spinners.** Async work (interaction spec §2.2) shows structure filling in, never a blocking blank (§8).
7. **Light, restrained, grown-up.** Plenty of paper/whitespace, hairline structure, type doing the hierarchy work. Character comes from type, color accents, and motion — not from ornament.

---

## 2. The shared spine

### 2.1 Brand anchor — Gulp Blue

One blue carries the brand across both surfaces. `--blue-600 #2563EB` is the primary. The difference between registers is **how much** blue, not **which** blue:

- **Web:** blue is *functional* — primary buttons, selection, focus, links, the `Due` accent. Everything else is slate. The accent earns attention by scarcity.
- **Mobile:** blue is *brand* — larger fills, the active tab, the capture button, headers; gentle blue→blue tints and (sparingly) gradients are allowed at hero moments.

### 2.2 Mastery-state language

The five states from interaction spec §F7, rendered identically everywhere (full tokens in §3.3). Day-to-day UI shows three states + two side-states; the fine-grained ladder lives only on Concept/Card detail and stats.

```
New      → "not started"   slate
Learning → "in progress"   amber
Known    → "mastered"      emerald
Due      → "do this now"   blue   (= the brand accent; due is a call to act)
At risk  → "forgetting"    red
```

Rendered as a **state chip** (§7.2): a tinted pill with a label, never a bare color swatch (accessibility, §9).

### 2.3 Type roles

Three families, fixed roles, shared across surfaces (concrete stacks and scale in §4):

| Family | Role | Where |
|---|---|---|
| **Inter** | the workhorse — UI, body, web headings | everywhere |
| **Geist Mono** | the apparatus — counts, intervals, streaks, metadata labels, coordinates | everywhere, for numbers & overlines |
| **Instrument Serif** | the voice — expressive hero/display lines | mobile hero moments, occasional web marketing headers |

Geist Mono on data is a deliberate spine thread: the "how many due / how many days / how long a streak" numbers look the same on phone and laptop, and the monospaced figures reinforce the product's "tracked, measured mastery" thesis.

### 2.4 The Card & shape language

The library is built from typed objects (interaction spec §4.2) and the unit of practice is the **Card**. The UI mirrors this: the **card** is the base container on both surfaces — a Snapshot in a list, a digest item, a Gulp prompt, a sediment proposal. Shared shape rules:

- Rounded rectangle, hairline border or soft shadow (register-dependent, §5.4), generous interior padding.
- A card always carries, where applicable: a **type glyph** (Snapshot / Conversation / Subscription / Concept), a **title**, **metadata in mono**, and a **state chip**.
- Radius and elevation differ by register (web tighter/flatter, mobile rounder/softer) but the anatomy is identical.

### 2.5 Spacing base & icons

- **4px base unit** for all spacing, both surfaces (§5.1). Density differs by *which* steps you reach for, not by the grid.
- **Icons:** one family, line style, 1.5px stroke, 24px default grid, rounded joins to match the friendly-but-precise tone. Type glyphs for the core objects are part of the set (§2.4).

### 2.6 Iconography conventions

- Line icons by default; filled variant reserved for the **active** state of navigation (mobile tab, web sidebar).
- Object glyphs are stable across the product: Snapshot (document), Conversation (chat), Subscription (broadcast/rss), Concept (node), Card (rectangle), Knowledge base (stack).
- Status uses chips + text, not icon-only, so meaning survives for color-blind users (§9).

### 2.7 Voice in UI (microcopy)

- **Plain and short.** "Add to library," "Start Gulp," "N due," "Save what I learned" — verbs, not features.
- **Web is neutral and precise** ("12 awaiting review", "Approve all"); **mobile is warm and encouraging** ("Nice — 3 mastered today", "You're on a 5-day streak") — but never cute at the cost of clarity.
- **Numbers are mono.** Any count, interval, or streak in copy is set in Geist Mono.
- **Never blame the user.** Failure states (§8) describe what happened and the next action ("Couldn't fully read this — retry or open original").

### 2.8 Motion principles

- **Shared easing:** `--ease-standard: cubic-bezier(.2, 0, 0, 1)`; `--ease-emphasized: cubic-bezier(.2, 0, 0, 1)` with longer duration for mobile celebration.
- **Web durations:** 120–180ms; functional, no bounce; transitions clarify cause→effect (selection, panel open).
- **Mobile durations:** 200–320ms; expressive *only at progress* — card advance, grade haptic, streak count-up, session-summary glow.
- **Reduced motion** (§9): celebration degrades to a simple fade; nothing essential depends on animation.

---

## 3. Color system

Light theme only (v1). Tokens are semantic where possible so a dark theme is a later swap (§10).

### 3.1 Brand — Gulp Blue

| Token | Hex | Use |
|---|---|---|
| `--blue-50` | `#EFF5FF` | tints: selected row, info banner bg, `Due` chip bg |
| `--blue-100` | `#DBE8FE` | hover tint, subtle fills |
| `--blue-500` | `#3B82F6` | secondary/hover on dark fills, mobile gradient stop |
| `--blue-600` | `#2563EB` | **primary** — buttons, active nav, links, focus, `Due` accent |
| `--blue-700` | `#1D4ED8` | pressed / active state |

### 3.2 Neutrals

Text ink is shared so prose reads identically; **surfaces and borders carry the only register difference** — web runs cool (slate), mobile runs a hair warmer (sand) for approachability. Everything stays light.

| Role | Token | Web (cool) | Mobile (warm) |
|---|---|---|---|
| App background | `--bg` | `#F8FAFC` | `#FAFAF7` |
| Surface / card | `--surface` | `#FFFFFF` | `#FFFFFF` |
| Subtle fill / hover | `--fill` | `#F1F5F9` | `#F4F3EE` |
| Border / hairline | `--border` | `#E2E8F0` | `#E9E6DD` |
| Strong border / disabled | `--border-strong` | `#CBD5E1` | `#D8D3C7` |
| Placeholder / `New` state | `--muted` | `#94A3B8` | `#A8A395` |
| Secondary text | `--text-2` | `#64748B` | `#6B665A` |
| Primary text / ink | `--text-1` | `#0F172A` | `#1C1B18` |

> Implementation note: ship these as one set of semantic tokens (`--bg`, `--surface`, `--text-1`…) with two value maps (`web`, `mobile`). Components reference the semantic name only.

### 3.3 Mastery-state palette (shared — do not localize per surface)

Each state has an **accent** (chip text/icon, progress fill) and a **tint** (chip background). Chip text uses the dark on-color token to clear contrast (§9), never the accent on white.

| State | Accent | Tint (chip bg) | On-tint text |
|---|---|---|---|
| **New** | `#94A3B8` | `#F1F5F9` | `#475569` |
| **Learning** | `#F59E0B` | `#FEF3C7` | `#92400E` |
| **Known** | `#10B981` | `#D1FAE5` | `#065F46` |
| **Due** | `#2563EB` | `#EFF5FF` | `#1D4ED8` |
| **At risk** | `#EF4444` | `#FEE2E2` | `#991B1B` |

The full ladder (`Unread → Read → Summarized → Can recall → Can distinguish → Can apply → Mastered`, plus `At risk`) is surfaced only on Concept/Card detail and stats as a graduated track using shades between `New` and `Known` (interaction spec §F7); the daily UI only ever shows the five above.

### 3.4 Functional / semantic

| Token | Hex | Use |
|---|---|---|
| `--success` | `#10B981` | confirmations (== Known) |
| `--warning` | `#F59E0B` | caution (== Learning) |
| `--danger` | `#EF4444` | destructive / `Needs attention` (== At risk) |
| `--info` | `#2563EB` | informational (== brand) |
| `--focus-ring` | `rgba(37,99,235,.45)` | 2px ring + 2px offset, both surfaces |
| `--overlay-scrim` | `rgba(15,23,42,.40)` | sheets, modals, `⌘K` |

Semantic colors deliberately reuse the mastery palette so the whole product speaks one color vocabulary.

### 3.5 Mobile expressive accents

Used **only** at genuine moments of progress (interaction spec §F4 session summary, grade, streak) and **never** on web or on working surfaces:

| Token | Hex | Use |
|---|---|---|
| `--celebrate-amber` | `#F59E0B` | streak flame, "correct!" flash, summary highlights |
| `--celebrate-glow` | `radial blue→transparent` | session-summary background glow |
| `--reward-gradient` | `linear(135°, #2563EB → #3B82F6)` | hero capture button, "mastered" badge burst |

Rule: amber is **complementary** to the blue brand — it gives mobile its warmth and reward energy without competing with blue for "act now." Amber is never used as body text (fails contrast, §9); it appears as fills, icons, and short emphatic numerals only.

### 3.6 Contrast budget

- Body text (`--text-1` on `--surface`/`--bg`): ≥ 7:1 (AAA).
- `--blue-600` on white and white on `--blue-600`: ≥ 4.5:1 (AA) — safe for buttons, links, UI text.
- State chips use the on-tint text tokens (§3.3) for ≥ 4.5:1.
- Amber and other low-contrast accents: decorative / fills only, always paired with a text label.

---

## 4. Typography

English / Latin only in v1 (CJK deferred, §10).

### 4.1 Families & stacks

| Name | Stack | Weights |
|---|---|---|
| **Inter** | `Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` | 400 / 500 / 600 / 700 |
| **Geist Mono** | `'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace` | 400 / 500 / 700 |
| **Instrument Serif** | `'Instrument Serif', Georgia, 'Times New Roman', serif` | 400 + italic |

Geist Mono and Instrument Serif already ship in `design/fonts/`; reuse them. (Inter replaces the poster's Young Serif/Work Sans pairing — the "Sediment" poster system is marketing-only and is not adopted here.)

### 4.2 Type scale (two scales, shared roles)

Web is denser; mobile is larger with bigger jumps. Sizes are `px / line-height`, tracking in em.

| Role | Family / weight | Web | Mobile | Tracking |
|---|---|---|---|---|
| **Display** | Instrument Serif 400 | 32 / 36 *(rare)* | 40 / 44 | −0.01 |
| **Title L** | Inter 600 | 22 / 28 | 28 / 34 | −0.01 |
| **Title M** | Inter 600 | 18 / 24 | 20 / 28 | −0.005 |
| **Title S** | Inter 600 | 15 / 20 | 17 / 24 | 0 |
| **Body L** | Inter 400 | 16 / 24 | 17 / 26 | 0 |
| **Body M** (default) | Inter 400 | 14 / 20 | 16 / 24 | 0 |
| **Body S** | Inter 400 | 13 / 18 | 14 / 20 | 0 |
| **Label / overline** | Geist Mono 500, UPPERCASE | 11 / 16 | 12 / 16 | +0.08 |
| **Caption** | Inter 400 | 12 / 16 | 13 / 18 | 0 |
| **Data / numerals** | Geist Mono 500, tabular | contextual | contextual | 0 |

- **Default body:** web `Body M` 14px (dense workbench); mobile `Body M` 16px (comfortable reading).
- **Hierarchy is type-led.** Prefer size/weight/space over rules and boxes to separate content.
- **Instrument Serif** is rationed: the onboarding aha line, a session-summary headline, an expressive empty state. One serif line per screen, maximum.

### 4.3 Numerals & mono

- All **counts, intervals, streaks, percentages, dates, and metadata keys** use Geist Mono with **tabular figures** so numbers don't jitter as they update (the `N due` badge, "+3 days", "5-day streak", review timestamps).
- **Overlines / section labels** use the Mono `Label` style (uppercase, tracked +0.08em) — the product's "clinical apparatus" voice, carried over as a brand thread without the poster aesthetic.

### 4.4 Text-style inventory (named, for components)

`display` · `title-l` · `title-m` · `title-s` · `body-l` · `body-m` · `body-s` · `label` · `caption` · `data`. Components reference these names, not raw sizes.

---

## 5. Spacing, grid & layout

### 5.1 Spacing scale (4px base, shared)

| Token | px | Token | px |
|---|---|---|---|
| `--space-1` | 4 | `--space-6` | 24 |
| `--space-2` | 8 | `--space-8` | 32 |
| `--space-3` | 12 | `--space-10` | 40 |
| `--space-4` | 16 | `--space-12` | 48 |
| `--space-5` | 20 | `--space-16` | 64 |

- **Web** reaches for 2/3/4 for in-component rhythm, 6/8 between regions.
- **Mobile** reaches for 4/5/6 in-component, 8/10/12 between regions (more air).
- Default screen gutter: web panels 24, mobile 16.

### 5.2 Web layout — the workbench

- **Three-pane where useful** (interaction spec §4.3): list ▸ reader ▸ pack/chat panel.
- **Left sidebar:** 240px (`Today · Inbox · Library · Feeds · Knowledge bases · Search · Settings`), collapsible to a 56px icon rail.
- **Reader / content column:** comfortable measure, max ~720px.
- **Right panel:** 360–420px for knowledge pack or conversation; dismissible.
- **`⌘K` command bar:** centered overlay (560px) on `--overlay-scrim`; handles search + capture + jump-to.
- **Breakpoints:** ≥1280 three-pane; 1024–1279 two-pane (right panel becomes an overlay); <1024 sidebar collapses to rail, panels stack.

### 5.3 Mobile layout — the daily ritual

- **Bottom tab bar (4):** `Today · Library · ⊕ Capture · You`; height 56 + safe-area inset. `⊕ Capture` is the raised center action (opens a sheet, produces a Snapshot), filled blue — the brand's most visible touchpoint.
- **Single-column content**, 16px gutters, comfortable line length.
- **Thumb zone:** primary actions and Gulp answers anchored to the lower third; reachable one-handed (interaction spec §9).
- **Gulp prompt:** full-bleed, no tab bar, one prompt per screen; answers/grade at the bottom (§7.7).
- **Sheets** (capture confirm, sediment): bottom sheets with a drag handle, rounded top corners (`--radius-xl`).

### 5.4 Radius, elevation & borders

| | Web (precise/flat) | Mobile (soft/friendly) |
|---|---|---|
| `--radius-sm` | 4 | 8 |
| `--radius-md` (cards) | 6 | 12 |
| `--radius-lg` | 8 | 16 |
| `--radius-xl` (sheets) | 12 | 20 |
| `--radius-pill` | 999 | 999 |
| Card separation | 1px `--border`, `--shadow-sm` on hover | `--shadow-card` |
| `--shadow-sm` | `0 1px 2px rgba(15,23,42,.06)` | — |
| `--shadow-card` | — | `0 2px 8px rgba(28,27,24,.08)` |
| `--shadow-overlay` | `0 8px 28px rgba(15,23,42,.14)` | `0 8px 28px rgba(28,27,24,.16)` |

- **Web leans on hairlines**, near-flat; **mobile leans on soft shadows**, rounder corners.
- **Hairlines** are 1px `--border`; reserve heavier dividers for true section breaks.

---

## 6. The two registers, in detail

### 6.1 Web register — precise productivity (B)

- **Feel:** Linear/Notion. Quiet, dense, fast, systematic. The workbench recedes so content and structure lead.
- **Color:** near-grayscale (slate ramp) with blue as the single functional accent — primary action, selection, focus, links, `Due`. Mastery chips are the only other color, and they earn it.
- **Density:** compact rows (40px), multi-column lists, persistent filter chips, three-pane.
- **Type:** 14px base, tight headings, generous use of the Mono `Label` for column headers and metadata.
- **Interaction:** keyboard-first — `⌘K`, `1–4` to answer in Gulp, `space` reveal, `enter` next, arrow navigation, type-to-filter.
- **Motion:** fast and functional (120–180ms); panels slide, selections highlight; no celebration.
- **Inbox/Library/Feeds** are the home of deep curation (interaction spec §F2): reader + pack side-by-side, split/merge Concepts, re-file into KBs.

### 6.2 Mobile register — characterful & rewarding (C)

- **Feel:** Arc — sophisticated with warmth and reward. Confident, friendly, a little expressive; *not* a cartoon mascot product. Personality comes from type (Instrument Serif moments), the blue brand, amber celebration, and motion.
- **Color:** amplified blue brand (active tab, capture button, headers, hero fills); amber/glow celebration at progress moments; warm-neutral surfaces.
- **Density:** comfortable single column, large tap targets (≥44px), big readable type (16px base).
- **Type:** bigger jumps; Instrument Serif for the onboarding aha, session-summary headline, and expressive empty states.
- **Interaction:** thumb-first; haptics on grade; voice input for "say it in your own words"; bottom sheets.
- **Motion:** expressive at progress — card advance, streak count-up, "mastered" badge burst, summary glow (all reduced-motion-safe, §9).
- **The Today screen is the emotional home** (interaction spec §2.4, §F4): the daily answer to "what should I do right now?", the `N due` badge, the digest stack, the `N new to confirm` card, and "Start Gulp."

---

## 7. Core components

Mapped to the interaction spec's key-screen inventory (§6) and core objects (§4.2). For each: anatomy, key variants/states, and any register difference.

### 7.1 Object card

The base container for any Source-derived object in a list (Snapshot, Conversation, Subscription item, digest item).

- **Anatomy:** type glyph · title (`title-s`) · 1–2 line summary (`body-s`, `--text-2`) · metadata row in mono (source, time, `+N cards`) · **state chip** (§7.2) · optional thumbnail.
- **Status overlays:** `Processing` (skeleton shimmer on the pack area, item still openable), `Needs attention` (amber left edge + banner, §8).
- **Web:** compact row, hairline separators, hover reveals quick actions (open, approve, discuss). **Mobile:** taller card, `--shadow-card`, swipe actions (archive / discuss).

### 7.2 Mastery state chip

The product's most-repeated component (interaction spec §2.3).

- **Anatomy:** pill, tinted background + on-tint text + optional 8px dot; label text always present (`New` / `Learning` / `Known` / `Due` / `At risk`).
- **`Due`** may render as a count badge ("`3 due`") in mono.
- Identical tokens on both surfaces (§3.3). Never color-only.

### 7.3 Filter chips (web Library)

- Horizontally scrolling, toggleable chips: by form (Snapshots · Conversations), by derived type (Cards · Concepts), by Knowledge base, by mastery / `Due` (interaction spec §4.3).
- Selected = `--blue-50` fill + `--blue-700` text + 1px blue border; idle = `--fill` + `--text-2`.

### 7.4 Buttons & primary actions

| Variant | Look | Use |
|---|---|---|
| **Primary** | `--blue-600` fill, white text | the one key action (Start Gulp, Add to library, Confirm) |
| **Secondary** | `--surface` + `--border`, `--text-1` | alternatives (Open original, Skip) |
| **Ghost** | text only, `--text-2` | low-emphasis (Dismiss, Snooze) |
| **Danger** | `--danger` text/fill | destructive (Discard) |

- One primary per screen (§1.2.2). Heights: web 32/36, mobile 48 (thumb).
- **Mobile hero buttons** (`⊕ Capture`, "Start Gulp") may use `--reward-gradient` and a soft shadow.

### 7.5 Capture confirm sheet (interaction spec §F1)

- **Anatomy:** detected title/type · target knowledge base (default Inbox) · optional one-line note · optional tags · Confirm.
- **Behavior:** lightweight; auto-confirms after a short timeout for true one-gesture capture; shows a "saved" toast, no waiting on processing.
- **Mobile:** bottom sheet from the OS share sheet / `⊕`. **Web:** `⌘K → paste` inline panel. Both write the same Inbox state.

### 7.6 Snapshot detail & knowledge pack (interaction spec §F2)

- **Web (deep curation):** three-pane — reader on one side, **knowledge pack** on the other (summary → background → key terms → people/orgs → core claims → counter-views → connections), each pack element a `suggested → kept / dismissed` block; **draft-cards review strip** along the bottom (`draft → accepted / rejected`).
- **Mobile (quick look):** stacked **segmented control** `Read · Pack · Cards`; full curation stays on web.
- Pack elements are cards (§2.4); kept/dismissed states use subtle check / strike affordances, not destructive color.

### 7.7 Gulp prompt & reveal — the hero (interaction spec §F4)

The product's signature screen; **one thing per screen, full-bleed, no competing chrome.**

- **Prompt card:** the question (`title-m`/`body-l`), prompt-type adapts (short-answer, MCQ, explain-it, apply-it, cloze, "say it in your own words"). Source context minimized until reveal.
- **Answering:** MCQ options as large tappable cards (mobile) / numbered `1–4` (web); text field for free response; mic for voice.
- **Reveal:** answer + source-grounded explanation; for free responses, brief AI feedback. A correct answer triggers a mobile "correct" flash (amber/emerald, reduced-motion-safe).
- **Self-grade:** three large controls — **`Got it` / `Fuzzy` / `Missed`** (emerald / amber / red), feeding the scheduler (interaction spec §F7). Haptic on grade (mobile).
- **Inline affordances:** "Explain more" (opens a mini Conversation, §7.10), "Why am I seeing this?", "Snooze".
- **Web:** keyboard throughout (`1–4`, `space`, `enter`). **Mobile:** all targets in the thumb zone.

### 7.8 Session summary (interaction spec §F4)

- Items reviewed · new mastered · still-fuzzy · **streak** · "what to gulp next."
- **Mobile = celebratory:** Instrument Serif headline, streak count-up, `--celebrate-glow`, amber highlights. **Web = a tidy stat block**, no celebration.
- Always offers a non-dead-end next step ("Keep going" / "Done"); empty/at-risk fallbacks per interaction spec §F4.

### 7.9 Today (interaction spec §4.3, §F6)

- **Anatomy (mobile-primary):** "what to do now" hero + **Start Gulp** · persistent **`N due`** badge · **Daily digest** card stack · **`N new to confirm`** batch-review card (the mobile form of review) · read-only "recently captured / processing" peek · "Continue where you left off" (interaction spec §8).
- **`N new to confirm` card:** approve-all, or tap through a quick accept/reject strip (lightweight batch review, interaction spec §F2). This is how mobile-only users close the loop (interaction spec §F8).
- **Web Today:** the same essentials, denser, with deep links into Inbox/Library.

### 7.10 Conversation & sediment (interaction spec §F5)

- **Thread:** message list with **citation chips** (linking to the underlying Source/pack/Concept); anchored-object context peek.
- **Web:** chat panel beside the reader. **Mobile:** full-screen chat with a collapsible "context" peek.
- **Sediment review sheet (identical both surfaces):** proposed new points, corrected misconceptions, candidate Cards, Concepts touched, "questions to review" — each `suggested → kept / dismissed`. Discard keeps the thread, creates nothing (no silent loss, §8).

### 7.11 Feeds & digest (interaction spec §F6)

- **Feeds list (web-primary):** per-subscription row — health (`active` / `muted` / `error`), unread count (mono), mute, **auto-approve toggle**.
- **Daily digest (mobile-primary):** ranked, reasoned cards ("why it's worth your time, how it connects"); per-item actions read / gulp / dismiss / send-to-Gulp; states `unseen / read / gulped / dismissed`.
- **Weekly review:** themes, concept evolution, "saved but not yet mastered," "at-risk" list — uses the full mastery ladder track (§3.3).

### 7.12 Navigation

- **Mobile:** bottom tab bar (§5.3); active item = filled glyph + blue label; `⊕ Capture` raised, blue.
- **Web:** left sidebar (§5.2); active item = `--blue-50` fill + blue text + 2px left blue marker; `⌘K` always available.

### 7.13 Inputs, forms & toggles

- **Text fields:** `--surface`, 1px `--border`, `--radius-md`; focus = `--focus-ring`. Web 32/36 tall; mobile 48.
- **Toggle** (e.g., **auto-approve**, interaction spec §F2/§F6): blue when on; clear on/off label for accessibility.
- **Tags / KB pickers:** chip-based, type-to-filter.

### 7.14 Feedback — toasts, badges, notifications

- **Toast:** bottom (mobile) / bottom-left (web), auto-dismiss, single action ("saved" + Undo). Never blocks.
- **Badges:** mono counts; `N due` is the canonical example.
- **Notifications** (interaction spec §F9): every one deep-links to a single next action; visual style matches OS but copy follows §2.7; rate-limited and opt-in.

---

## 8. Cross-cutting states

Visual treatment for the states every list/object screen must define (interaction spec §7). The interaction is specified there; here is how each *looks*.

| State | Visual treatment |
|---|---|
| **Loading** | Skeletons matching final layout (card/row shapes), subtle shimmer; lists stay interactive as items stream in. Never a centered spinner on blank. |
| **Empty** | Purposeful, points to the next action. **Mobile:** expressive — Instrument Serif line + illustration-light mark + primary CTA (capture / subscribe / start onboarding). **Web:** terse — one line + CTA. |
| **Processing** | Item visible and openable; pack region shows skeleton; a small mono "processing" tag; flips to `Ready` with a quiet transition (interaction spec §2.2). |
| **Error / failed extraction** | Keep the Snapshot; amber left edge + "Couldn't fully read this" banner + **Retry** + **Open original**. `Needs attention` chip. Never destructive-red unless data loss is real. |
| **Offline** | Subtle persistent offline indicator (mono label in the top bar); captures queue (`Queued (offline)` chip); reads from cache; Gulp runs on cached due items; sync on reconnect. |
| **Limit / quota** | Soft-degrade: queue rather than block, explain in plain copy with the next step. |

---

## 9. Accessibility & input

- **Contrast** meets the budget in §3.6 (body ≥ 7:1; interactive ≥ 4.5:1). Low-contrast accents (amber, tints) are never the sole carrier of meaning.
- **State is never color-only:** mastery and status always pair color with a text label (§7.2).
- **Targets ≥ 44px** on mobile; primary actions in the thumb zone (interaction spec §9).
- **Keyboard (web):** full control — Gulp answers `1–4`, reveal `space`, next `enter`, capture `⌘K`; visible `--focus-ring` on every focusable element; logical tab order.
- **Mobile input:** haptics on grade; voice input for "say it in your own words"; respects Dynamic Type (scale the §4.2 mobile column) and large-text reflow.
- **Reduced motion:** celebration and transitions degrade to fades; nothing essential depends on animation (§2.8).
- **Screen readers:** object cards expose type, title, and mastery state; citation chips expose their source.

---

## 10. Deferred / open questions

**Deferred (v1):**

- **Dark theme** — tokens are authored as semantic roles (§3.2) so a dark "ink-ground" theme is a later value swap, not a redesign. Web (Linear-like) is the natural first candidate.
- **CJK typography** — the initial wedge is Chinese-language power users, but v1 ships English / Latin only (web and mobile both). A later pass defines CJK pairing (a Song/serif for display, a Hei/grotesque for body), mixed zh+en rules, punctuation, and line-height — likely landing on mobile first (the consumption end).
- **Illustration / mark system** for mobile empty and celebration states — directional only here (Instrument Serif + light marks); a fuller spec is later. No mascot in v1.
- **Full iconography source** (which icon set / custom draws for object glyphs) and a **detailed motion spec** (per-component curves and durations) are component-level docs.

**Open questions:**

- Should mobile's warm neutral ramp (§3.2) be this subtle, or lean further from web's cool slate for more distinct character?
- Is one functional blue accent enough for web's `Due` + primary + selection + links, or do `Due` and "primary action" need to be visually separated to avoid overload on dense screens?
- Does the Instrument Serif "voice" earn its place on web at all, or should web be Inter-only?
- How expressive should mobile celebration go before it reads as gamified rather than rewarding?

---

*Companion docs: [`00-product-one-pager.md`](00-product-one-pager.md) (what/why), [`01-interaction-spec.md`](01-interaction-spec.md) (how the user moves). Proposed next: `02-data-model.md`, and component-level specs for iconography and motion.*
