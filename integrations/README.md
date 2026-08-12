# integrations/ — per-agent client configs for the Gulp MCP channel

The Gulp API exposes pending digest/cards jobs over MCP
(`POST <api-url>/mcp`, PAT-authenticated — spec
`docs/superpowers/specs/2026-07-16-mcp-agent-jobs-design.md`). Jobs are
self-describing, so any MCP client can run them; the configs here are thin
orchestrators per agent.

An agent can also **create** its own digest jobs: `list_jobs(include_candidates:
true)` surfaces captures that were never routed anywhere (`state:
"unpublished"`), and `publish_job(snapshot_id)` turns one into a job. So the
whole path from "forward a paper" to "pack in the Library" runs without a
browser — the web Export button is the manual equivalent, not a prerequisite.

## Claude Code

1. Create a PAT: Gulp web → Settings → API tokens → Generate.
2. Connect the MCP server:

   ```bash
   claude mcp add --transport http gulp https://<your-api-host>/mcp \
     --header "Authorization: Bearer gulp_pat_..."
   ```

   On the Railway+Vercel deployment the API has no separate public host — the
   Next rewrite proxies `/api/*` to it, so the URL is
   `https://<your-web-host>/api/mcp`.

3. Install the skill (symlink so `git pull` updates it):

   ```bash
   ln -s "$(pwd)/integrations/claude-code/gulp-work" ~/.claude/skills/gulp-work
   ```

4. In any Claude Code session: `/gulp-work` (or `/gulp-work cards`).

## Codex (deferred)

Same MCP server. A config snippet + AGENTS.md note lands here when needed;
clients without HTTP transport can bridge with `mcp-remote` (stdio).
