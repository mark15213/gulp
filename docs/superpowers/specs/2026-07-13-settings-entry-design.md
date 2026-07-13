# Settings entry page — design

**Date:** 2026-07-13
**Status:** approved for implementation
**Subsystem:** `apps/web` shell — activates the `Settings` nav destination (`docs/01 §7.1` nav, `docs/01 §306`, `docs/03 §268`)

## 1. Problem & goal

The MaaS/BYOK work (spec 2026-07-13) shipped its settings page at `/settings/ai` but surfaced it as a bare "AI" link inside the account menu — a one-off entry that ignores the product's existing nav design: the sidebar already renders a **disabled "Settings" placeholder** ("Coming soon") and `docs/01` names Settings a first-class destination.

**Goal:** activate the Settings destination as a single entry page that hosts the AI configuration and previews future sections, and remove the stray account-menu link.

## 2. Decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Structure | **Single entry page** (user-picked): `/settings` lists section cards; clicking an active card navigates to its full page. No two-pane settings layout. |
| D2 | Sections | Active: **AI models** → `/settings/ai`. Greyed ("Coming soon", non-clickable): **Account** (profile, password), **Preferences** (language, appearance), **Notifications** (`docs/01 §286/§306`). |
| D3 | Sidebar | The disabled footer placeholder becomes a real link to `/settings` with route-active highlighting (new `SettingsLink` client component; reuses the existing sidebar item styles). |
| D4 | Account menu | The "AI" link added by the BYOK slice is **removed**; the menu returns to avatar + logout. |
| D5 | AI page | `/settings/ai` unchanged except a "← Settings" back link for navigation. |

**Non-goals:** implementing Account/Preferences/Notifications (cards are inert placeholders); any backend change.

## 3. Components

- `apps/web/app/settings/page.tsx` — the entry page; renders `SettingsHome`.
- `apps/web/components/settings/SettingsHome.tsx` (+ module.css + test) — card list: one `Link` card (AI models) + three `aria-disabled` cards with a "Coming soon" chip.
- `apps/web/components/shell/SettingsLink.tsx` (+ test) — client component (`usePathname`) rendering the sidebar footer link, active on `/settings` and its subtree.
- `apps/web/components/shell/Sidebar.tsx` — footer placeholder replaced by `<SettingsLink />`.
- `apps/web/components/shell/AccountMenu.tsx` — "AI" link and its style/test removed.
- `apps/web/components/settings/AISettings.tsx` — back link at the top.

## 4. Testing

- `SettingsHome`: AI card links to `/settings/ai`; greyed cards are `aria-disabled` and not links.
- `SettingsLink`: renders href `/settings`; active state on `/settings/ai`.
- `AccountMenu` test drops the AI-link case.
- Existing suites stay green (`pnpm turbo test`, eslint, `tsc --noEmit`).
