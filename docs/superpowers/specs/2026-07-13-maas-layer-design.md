# Unified model-access (MaaS) layer with BYOK — design

**Date:** 2026-07-13
**Status:** approved for planning
**Subsystem:** cross-cutting — `services/shared/gulp_shared/llm` + API settings surface + web settings page

## 1. Problem & goal

Every AI feature in Gulp (pack pipeline digest/cards, reader chat) funnels through `gulp_shared/llm`, which today has exactly one capability (`complete_json` — non-streaming structured output), one provider (`AnthropicProvider`), and one server-wide API key (`settings.anthropic_api_key` from env). Users cannot bring their own key, choose a provider, or use any model besides the configured Claude model, and the layer cannot express streaming, tool use, or multimodal input.

**Goal:** turn `gulp_shared/llm` into a unified model-access layer supporting **Claude, OpenAI, DeepSeek, and Qwen**, where each user supplies their own API keys (BYOK) and picks one default provider + model that all AI features use. The layer must expose four capabilities: structured JSON output (existing), streaming text chat, a tool-use/agent loop, and multimodal (image) input.

## 2. Decisions (locked during brainstorming)

| # | Decision | Choice |
|---|---|---|
| D1 | Scope | **In-Gulp upgrade** of the existing `gulp_shared/llm` layer — not a standalone gateway service. |
| D2 | Key model | **Pure BYOK.** Users must supply their own keys to use AI features. `settings.anthropic_api_key` survives only as a dev/test fallback (used when a user has no credentials AND the env var is set); production leaves it unset. |
| D3 | Capabilities | All four: structured JSON (must keep working), streaming chat, tool-use loop, multimodal input. |
| D4 | Model selection | **Global single choice** — the user picks one default `provider + model`; every feature uses it. No per-feature or per-conversation model picking (deferred). |
| D5 | Implementation | **Hand-rolled, two wire adapters** (approach A). DeepSeek and Qwen (DashScope compatible-mode) speak the OpenAI wire format, so 4 providers = `AnthropicAdapter` + `OpenAICompatAdapter`. No LiteLLM, no gateway service. Only new runtime dependencies: `openai` SDK and `cryptography`. |

**Non-goals (deferred):** per-feature model assignment, per-conversation model picker UI, dynamic model-list fetching from provider APIs, a product-level agent feature (only the loop *mechanism* ships), provider usage/cost accounting, key sharing between users.

## 3. Contract layer (`gulp_shared/llm/base.py` rework)

### 3.1 Message model (provider-neutral)

```python
TextPart(type="text", text: str)
ImagePart(type="image", media_type: str, data_b64: str)      # multimodal
ContentPart = TextPart | ImagePart
ChatMessage(role: "system"|"user"|"assistant"|"tool",
            content: str | list[ContentPart],
            tool_calls: list[ToolCall] | None,               # assistant turns
            tool_call_id: str | None)                        # tool-result turns
ToolSpec(name: str, description: str, input_schema: dict)     # declared to the model
ToolCall(id: str, name: str, arguments: dict)                 # emitted by the model
StreamEvent = TextDelta(text) | ToolCallEvent(tool_call) | UsageEvent(input_tokens, output_tokens) | DoneEvent(stop_reason)
```

The existing `Message = dict[str, str]` alias is replaced by `ChatMessage`; call sites migrate mechanically.

### 3.2 Provider protocol — two methods

```python
class LLMProvider(Protocol):
    async def complete_json(*, system, messages, json_schema, config) -> dict   # existing semantics
    def stream_chat(*, system, messages, tools: list[ToolSpec] | None, config) -> AsyncIterator[StreamEvent]
```

- `complete_json` — structured output. Implemented on **both** wires via a **forced tool/function call** (the only structured-output mechanism all four providers support). `complete_structured` (Pydantic validation + retry) is unchanged.
- `stream_chat` — one method covers plain streaming chat (`tools=None`) and agent tool steps (`tools` passed → may yield `ToolCallEvent`s).

### 3.3 ModelConfig carries the credential

```python
class ModelConfig(BaseModel):
    provider: str
    model: str
    api_key: SecretStr
    base_url: str | None = None      # filled from ProviderSpec
    max_tokens: int = 4096
    temperature: float = 0.2
```

Clients are constructed per call from the config — no module-level client holding a baked-in key.

### 3.4 Registry becomes a spec catalog

`register_provider(name, instance)` is replaced by a static catalog:

```python
ProviderSpec(adapter: type, base_url: str, capabilities: frozenset[Capability],
             models: list[ModelInfo])          # curated model list for the UI
Capability = {"json", "stream", "tools", "vision"}
```

| provider | adapter | base_url | capabilities |
|---|---|---|---|
| `anthropic` | `AnthropicAdapter` | official SDK default | json, stream, tools, vision |
| `openai` | `OpenAICompatAdapter` | `https://api.openai.com/v1` | json, stream, tools, vision |
| `deepseek` | `OpenAICompatAdapter` | `https://api.deepseek.com` | json, stream, tools (**no vision**) |
| `qwen` | `OpenAICompatAdapter` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | json, stream, tools, vision (VL models) |

Capabilities gate calls *before* they hit the wire (e.g. an image sent to DeepSeek raises `LLMCapabilityError` locally).

Curated model lists are pinned to current stable model ids at implementation time (e.g. anthropic: sonnet/haiku tiers; openai: gpt-4.1/gpt-4.1-mini; deepseek: deepseek-chat/deepseek-reasoner; qwen: qwen-plus/qwen-vl-plus). Updating the list later is a constant edit, not a schema change.

### 3.5 Adapters

- `AnthropicAdapter` — extends the existing provider: keeps forced-tool-use `complete_json`; adds `stream_chat` over the Messages streaming API (content-block deltas → `StreamEvent`s; `tool_use` blocks → `ToolCallEvent`).
- `OpenAICompatAdapter` — new, built on the `openai` SDK with `base_url` + `api_key` from config. `complete_json` = forced `tool_choice` function call; `stream_chat` = chat-completions streaming (aggregates function-call argument fragments into complete `ToolCallEvent`s).

### 3.6 Agent loop is pure logic, not an adapter concern

`gulp_shared/llm/loop.py`:

```python
async def run_tool_loop(*, system, messages, tools: list[ToolSpec],
                        executor: Callable[[ToolCall], Awaitable[str]],
                        config: ModelConfig, max_iters: int = 8) -> AsyncIterator[StreamEvent]
```

Repeatedly calls `stream_chat`, executes emitted tool calls via `executor`, appends tool-result messages, continues until the model stops or `max_iters` is hit. Ships with unit tests only — no product agent feature this round.

## 4. BYOK data model & key management

### 4.1 Storage (hangs off the S0 user system)

- New table `user_llm_credentials`: `id`, `user_id → users.id` (indexed), `provider: str`, `api_key_encrypted: bytes`, `created_at`, `updated_at`; unique `(user_id, provider)`. One row per provider; a user may configure all four.
- Default selection: two nullable columns on `users` — `llm_provider`, `llm_model`. NULL = not configured.
- One Alembic migration covers both.

### 4.2 Encryption

Fernet symmetric encryption (`cryptography`), keyed by a new `settings.credential_secret` (independent from `auth_secret` so the two rotate independently). Plaintext keys exist in memory only at call time; **no API response ever returns a plaintext key** — list endpoints return a mask (`sk-…abcd`, last 4 chars).

### 4.3 API surface (`/me/llm`, logic in `services/api/app/services/llm_settings.py`)

- `GET /me/llm` — configured providers (masked), current default provider/model, and the full provider catalog (capabilities + curated models) for the web UI.
- `PUT /me/llm/credentials/{provider}` — set/replace a key. Performs a **live validation ping** (minimal-token call) before persisting; an invalid key is rejected and not stored.
- `DELETE /me/llm/credentials/{provider}` — remove the key; if it backs the current default provider, the default is cleared too.
- `PUT /me/llm/default` — set default provider+model; requires a stored credential for that provider and a model from the catalog.

### 4.4 Web settings page

New "AI models" settings page reachable from the account menu: one card per provider (enter key / masked state / delete) plus a default provider+model selector fed by the catalog from `GET /me/llm`.

## 5. Call paths

### 5.1 Key resolution — single entry point

`gulp_shared/llm/resolve.py::resolve_model_config(session, user_id) -> ModelConfig` — loads the user's default provider/model, decrypts the matching credential, returns a ready `ModelConfig`. If unconfigured: falls back to the dev env key when present, else raises `LLMNotConfiguredError`. Both API and worker use only this function.

### 5.2 Reader chat goes streaming

The current non-streaming `ChatAnswer(answer, block_refs)` flow is replaced by an SSE endpoint. The model is prompted to cite blocks **inline** with markers (`[[block:ID]]`); tokens stream to the client as they arrive; when the stream ends the server parses the markers into `block_refs` and persists the `PackMessage` exactly as today. The web chat renders incrementally; block-highlight behaviour is unchanged.

### 5.3 Worker pipeline

Tasks resolve the owner's config at job start via `Source.owner_id` (already present — queue payloads unchanged) and pass the explicit `ModelConfig` into the existing `complete_structured` calls.

## 6. Error handling

`LLMError` gains typed subclasses; upper layers act on type:

| Error | Trigger | Handling |
|---|---|---|
| `LLMNotConfiguredError` | user has no key | API → structured error code `llm_not_configured`; web shows a "go to settings" CTA; worker marks the job failed with this reason |
| `LLMAuthError` | invalid/revoked key | same surface, "key invalid — check settings" copy; **never retried** |
| `LLMRateLimitError` | 429 / throttling | worker: arq backoff retry; chat: "try again shortly" |
| `LLMCapabilityError` | unsupported capability (e.g. image → DeepSeek) | blocked by the pre-flight capability check with a clear message |

## 7. Testing

- **Adapters:** recorded request/response fixtures per wire format — request shaping (system placement, tool declaration, image encoding) and response parsing (stream-event slicing, tool-call fragment aggregation). No live network.
- **Service layer:** fake provider injection (existing style) — `complete_structured` retry, `run_tool_loop` multi-round + `max_iters`, SSE event ordering.
- **API:** credentials CRUD (masked output, encrypt/decrypt roundtrip, failed validation not persisted), default-setting preconditions, `llm_not_configured` path.
- **Web:** settings-page interactions; chat streaming rendering against a mocked SSE source.
- Existing `test_llm_service.py` / `test_llm_wiring.py` update alongside the contract rework.

## 8. Delivery slices (each independently shippable)

1. **Contract rework + both adapters** — env key only, no product behaviour change; all existing tests green.
2. **BYOK** — credentials table + `/me/llm` endpoints + web settings page; `resolve_model_config` wired into chat and worker.
3. **Streaming chat** — SSE endpoint + inline citation markers + web incremental rendering.
4. **Tool loop** — `run_tool_loop` mechanism + tests (no product feature).
