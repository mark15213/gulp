# Subscription System — RSSHub/Folo-compatible feeds

Date: 2026-07-09
Status: Approved (design); pending implementation
Scope: `services/shared` (model + migration), `services/worker` (fetch loop),
`services/api` (feeds router/service + catalog), `apps/web` (Feeds + Discover
pages), `infra` (self-hosted RSSHub), and doc amendments to `docs/01·02·04`.

## Goal

Re-derive the dropped S7 "Feeds" subsystem (docs/04 amendment 2026-07-06) as a
**subscription pipeline only** — follow a feed, poll it, browse new entries,
and explicitly promote ("gulp") an entry into the existing snapshot pipeline.
The AI-ranked Daily digest of `01 §F6` stays out of scope for this slice.

Compatibility target: the **RSSHub / Folo ecosystem**. A subscription's
address is stored in Folo's instance-independent `rsshub://namespace/path`
convention (or a plain `https://` RSS/Atom URL), and the entire open-source
RSSHub route catalog (`routes.json`, ~1,675 namespaces) is browsable and
subscribable from a Discover surface.

## Decisions (owner-approved 2026-07-09)

1. **v1 scope = subscription pipeline only.** No digest, no AI ranking. The
   `auto_approve` field of `02 §4.8` is parked with the snapshot gate; OPML
   import/export is a fast-follow, not v1.
2. **Entries are lightweight `FeedEntry` rows, not auto-created Snapshots.**
   Fetched items live in a separate prunable table and are browsed on the
   Feeds surface; only an explicit **Gulp** promotes an entry to a
   `Source(kind=snapshot)` through the normal capture pipeline. The library
   is never flooded by a noisy feed.
3. **RSSHub is self-hosted in `infra/docker-compose.yml`.** The public
   rsshub.app instance now throttles feed readers (verified 2026-07-09). The
   base URL is a setting (`rsshub_base_url`), so it can later point at a
   cloud instance.
4. **Discover = searchable catalog + paste.** The backend caches the official
   `routes.json`; the web client searches it (ranked by official `heat`).
   Folo-style dynamic parameter forms are out of scope; examples prefill a
   dialog and parameters are hand-edited. A paste box accepts `rsshub://`,
   a bare route path, or a plain `https://` feed URL.
5. **Architecture = `Source(kind=subscription)` + `feed_entries` table**
   (approach A). Subscriptions reuse the single-table discriminator model
   (`02` D1); promoted snapshots point back via `Source.emitted_by` — the
   field reserved for S7 in `source.py`.
6. **Subscription health is derived, not stored.** The old `02 §4.8` status
   domain (`active/muted/error`) would collide with the existing
   `snapshot_status` Postgres enum on `Source.status`. Instead: `muted`
   (bool) + `last_fetch_error` (text, null = healthy) derive the three
   states; `unread_count` is derived from `feed_entries`. No enum surgery,
   no stored counters. `docs/02 §4.8` is amended accordingly.

## 1. Data model (`services/shared`)

### 1.1 `Source` — new nullable subscription-kind columns

| Field | Type | Notes |
|---|---|---|
| `feed_url` | `str?` | canonical address: `rsshub://ns/path` or `https://…`; unique per owner (soft-enforced in service) |
| `muted` | `bool?` | stop polling, keep data |
| `last_fetch_at` | `timestamp?` | |
| `last_fetch_error` | `text?` | null = healthy; set/cleared each fetch |
| `feed_etag` / `feed_http_modified` | `str?` | conditional GET (HTTP 304) |
| `consecutive_failures` | `int?` | drives retry back-off (§4) |

`Source.status` for subscription rows is set to `ready` at creation and never
changes — health is derived (decision 6).

### 1.2 `Source.emitted_by` (snapshot rows)

`emitted_by: uuid? → sources.id` (FK `ON DELETE SET NULL`, index). Set when a
snapshot was promoted from a feed entry; null for ad-hoc captures. This is
the `02 §4.3` field deferred at S2.

### 1.3 `CapturedVia`

Add enum value `feed` (Postgres `ALTER TYPE … ADD VALUE`).

### 1.4 New table `feed_entries`

| Field | Type | Notes |
|---|---|---|
| `id` | `uuid` pk | |
| `subscription_id` | `→ sources.id` | FK `ON DELETE CASCADE`, index |
| `guid` | `str` | feed-provided id; fallback `sha256(link + title)`; **unique together with `subscription_id`** |
| `title` | `str` | |
| `url` | `str?` | entry link; entries without one cannot be promoted (v1) |
| `author` | `str?` | |
| `published_at` | `timestamp?` | |
| `content_html` | `text?` | feed-provided content — powers the reading pane |
| `read_at` | `timestamp?` | null = unread |
| `promoted_source_id` | `→ sources.id?` | FK `ON DELETE SET NULL`; set on gulp; doubles as the "already gulped" dedup record |
| `created_at` / `updated_at` | | `TimestampedBase` |

One Alembic migration covers 1.1–1.4.

## 2. Fetch pipeline (`services/worker`, arq)

1. **`poll_feeds`** — arq cron, every 30 min. Selects subscriptions that are
   not muted and due (default interval 30 min; back-off per §4), enqueues one
   `fetch_feed(subscription_id)` job each. Isolation: one bad feed never
   affects the rest.
2. **`fetch_feed(subscription_id)`** —
   - resolve address: `rsshub://ns/path` → `{settings.rsshub_base_url}/ns/path`;
     `https://` URLs pass through;
   - conditional GET with stored etag / last-modified; on 304, touch
     `last_fetch_at` and stop;
   - parse with **`feedparser`** (one parser for RSS 2.0 + Atom, both
     address forms);
   - upsert entries by `(subscription_id, guid)` — insert new, skip known;
   - update `last_fetch_at`, clear `last_fetch_error` and
     `consecutive_failures` on success; on failure record the error and
     increment the counter;
   - on first successful fetch, if the subscription title is still the
     address placeholder (user gave none at creation), backfill it with the
     feed's own title.
3. **`prune_feed_entries`** — weekly cron. Deletes unpromoted entries older
   than 90 days; promoted entries are kept (they are the dedup record and
   carry `emitted_by` context).
4. **Promotion is not a worker job** — the API creates the snapshot row and
   enqueues the existing `process_snapshot`; the genre-aware pipeline
   (articles zero-LLM, papers → digest) takes over unchanged. Capture never
   blocks on AI (repo Rule 4).

New Python dependency: `feedparser` (worker only).

## 3. API (`services/api` — new `routers/feeds.py` + `services/feeds.py`)

Routers stay thin (repo Rule 3). After implementation: `just gen-client`.

| Endpoint | Behaviour |
|---|---|
| `POST /subscriptions` | body `{feed_url, title?}`. Normalizes input (`rsshub://…`, bare `/ns/path` → `rsshub://ns/path`, or `https://…`); same-owner same-address returns the existing row (idempotent). Creates the `Source(kind=subscription, status=ready)` with placeholder title, then enqueues an immediate `fetch_feed`. No network I/O in the request. |
| `GET /subscriptions` | list + derived health (`active`/`muted`/`error`) + derived unread count |
| `PATCH /subscriptions/{id}` | `title`, `muted` |
| `DELETE /subscriptions/{id}` | deletes subscription; entries cascade; promoted snapshots survive (`emitted_by` → null) |
| `POST /subscriptions/{id}/refresh` | enqueue `fetch_feed` now |
| `GET /subscriptions/{id}/entries` | paginated, `unread_only` filter |
| `GET /feed-entries` | the cross-subscription "All" view, same filters |
| `POST /feed-entries/{id}/read` / `…/unread` | read-state toggle |
| `POST /subscriptions/{id}/read-all` | bulk mark-read |
| `POST /feed-entries/{id}/gulp` | creates `Source(kind=snapshot, origin_url=entry.url, captured_via=feed, emitted_by=subscription, status=queued)` via the existing capture service, enqueues `process_snapshot`, sets `promoted_source_id`. Idempotent: already-promoted entries return the existing snapshot id. 422 if the entry has no URL. |
| `GET /feeds/catalog/search?q=` | catalog search (§3.1) |

### 3.1 Route catalog

- Lazy-fetch `https://docs.rsshub.app/routes.json` (~7 MB, 1,675 namespaces)
  into Redis with a 7-day TTL; keep the parsed form in process memory.
- Search: substring match on namespace key/name and route name/path, ranked
  by official `heat`; results carry route path, parameter docs, `example`,
  and the `requireConfig` flag (surfaced in the UI as "needs instance
  config").
- The self-hosted instance's `/api/namespace` is *not* used — it lacks
  `heat`/`topFeeds` metadata.

## 4. Error handling

- **Fetch failure** (network / 404 / parse): recorded on the subscription,
  shown as a red health dot + message on Feeds; never blocks other
  subscriptions or any other subsystem (`01 §F6` principle). Retries next
  cycle; after **5 consecutive failures** the feed drops to a daily retry
  until it succeeds once.
- **Malformed feeds**: feedparser is tolerant; only bozo *and* zero entries
  counts as a failure.
- **Duplicate add**: normalized-address match returns the existing
  subscription (idempotent, not an error).
- **Entry without URL**: Gulp action disabled (v1 promotes by URL only).
- **rsshub.app throttling**: not applicable — all fetching goes through the
  self-hosted instance.

## 5. Web UI (`apps/web`)

- **`/feeds`** (web-primary per `03 §7.11`) — three panes:
  left = subscription list (health dot, mono unread count, mute toggle);
  middle = entry list (All | per-subscription, unread filter);
  right = reading pane rendering `content_html`, with actions **Forward** /
  open original / mark read. After forwarding, the entry shows a "Forwarded ✓"
  marker linking to the snapshot — which lands in the **Inbox** and reaches the
  **Library** only once processing completes (`status=ready`). Sidebar gains the
  `Feeds` item already reserved in `03 §5`.
- **`/feeds/discover`** — search box over the catalog; results grouped by
  namespace, heat-ranked; clicking an example prefills the subscribe dialog
  (parameters hand-editable); a persistent paste box accepts all three
  address forms. A built-in "starter list" section shows the recommended
  sources (§7).

## 6. Infra & settings

- `infra/docker-compose.yml`: add `rsshub` service (`diygod/rsshub` image,
  port 1200, reusing the existing `redis` service as its cache backend);
  comes up with `just up`.
- `gulp_shared/settings.py`: `rsshub_base_url` (default
  `http://localhost:1200`), `feed_poll_interval_minutes` (default 30),
  `feed_entry_retention_days` (default 90).

## 7. Recommended test sources (verified zero-config, 2026-07-09)

Chosen to cover: both address forms × three genres × zh/en × high/low volume.

Via the self-hosted RSSHub instance:

| Source | Why |
|---|---|
| `rsshub://anthropic/research` | English AI research articles — article-genre workhorse |
| `rsshub://sspai/index` | 少数派 front page — Chinese long-form, **high volume** (flood test) |
| `rsshub://qbitai/category/资讯` | 量子位 — Chinese AI news |
| `rsshub://solidot/www` | short newsy items (note-genre boundary) |
| `rsshub://36kr/hot-list` | ranked-list feed (entries = link aggregation) |
| `rsshub://hellogithub/volume` | monthly — **low volume** (304 / empty-fetch path) |
| `rsshub://v2ex/topics/hot` | forum threads (reading-pane `content_html` test) |
| `rsshub://readhub/daily` | one entry per day, predictable cadence |

Plain RSS/Atom (exercises the non-RSSHub path):

| Source | Why |
|---|---|
| `https://www.ruanyifeng.com/blog/atom.xml` | 阮一峰 — weekly, Chinese classic |
| `https://rss.arxiv.org/rss/cs.AI` | arXiv official — **paper genre + existing arxiv adapter**, end-to-end |
| `https://simonwillison.net/atom/everything/` | English AI blog, daily |
| `https://hnrss.org/best` | pure link aggregation (promotion = fetch-external-original stress test) |

These double as the Discover page's built-in starter list.

## 8. Testing

- **worker** (`cd services/worker && uv run pytest`): `fetch_feed` against
  local RSS/Atom fixture files, zero network — dedup upsert, guid-fallback
  hashing, `rsshub://` resolution, error recording + back-off counter,
  304 handling, title backfill.
- **api**: subscription CRUD, idempotent create, promotion (queue mocked),
  catalog search over a small `routes.json` fixture slice.
- **web**: vitest (classic JSX transform — JSX files need `import React`)
  for subscription-list and entry-list component states.

## 9. Doc amendments (fold-back)

- `docs/02 §4.8`: replace the stored `status`/`unread_count`/`auto_approve`/
  `feed_type` field set with the derived-health model and the v1 columns of
  §1.1 (decisions 1 & 6); add `feed_entries` to §4 and the ER diagram;
  `emitted_by` moves from deferred to live.
- `docs/01 §F6`: mark the digest half as still-deferred; subscription half
  implemented per this spec.
- `docs/04`: note that the subscription slice of the dropped S7 has been
  re-derived by this spec (the digest half remains dropped).

## 10. Out of scope (explicit)

- Daily digest / AI ranking (`01 §F6` step 3-4) — next iteration.
- `auto_approve` (parked with the snapshot gate), OPML import/export,
  newsletter/channel feed types (`feed_type` enum unnecessary until then),
  per-feed poll intervals, Folo-style dynamic parameter forms,
  `requireConfig` routes (need instance credentials).
