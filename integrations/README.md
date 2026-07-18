# integrations/ — per-agent client configs for the Gulp MCP channel

The Gulp API exposes pending digest/cards jobs over MCP
(`POST <api-url>/mcp`, PAT-authenticated — spec
`docs/superpowers/specs/2026-07-16-mcp-agent-jobs-design.md`). Jobs are
self-describing, so any MCP client can run them; the configs here are thin
orchestrators per agent.

## Claude Code

1. Create a PAT: Gulp web → Settings → API tokens → Generate.
2. Connect the MCP server:

   ```bash
   claude mcp add --transport http gulp https://<your-api-host>/mcp \
     --header "Authorization: Bearer gulp_pat_..."
   ```

3. Install the skill (symlink so `git pull` updates it):

   ```bash
   ln -s "$(pwd)/integrations/claude-code/gulp-work" ~/.claude/skills/gulp-work
   ```

4. In any Claude Code session: `/gulp-work` (or `/gulp-work cards`).

## Codex (deferred)

Same MCP server. A config snippet + AGENTS.md note lands here when needed;
clients without HTTP transport can bridge with `mcp-remote` (stdio).
