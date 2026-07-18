"""Job-archive entry names — the builder↔claim contract (spec 2026-07-16 §3).

The worker's export builder writes these entries into the job `.zip`; the API's
`claim_job` reads them back out and maps them onto the self-describing tool
payload. Both sides MUST agree on the exact names, so they live here as the
single source of truth — a rename that touches only one side becomes an
import-level break rather than a silent claim→rebuild loop.
"""

# Shared by both job kinds
INSTRUCTIONS_MCP = "instructions.mcp.md"
MANIFEST = "manifest.json"

# Digest job
INPUT_NORM_DOC = "input/norm_doc.json"
SCHEMA_PACK = "schema/pack.schema.json"

# Cards job
INPUT_PACK = "input/pack.md"
INPUT_CONVERSATION = "input/conversation.md"
SCHEMA_CARDS = "schema/cards.schema.json"
