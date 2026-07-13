// BYOK LLM settings helpers (spec 2026-07-13). Same pattern as index.ts:
// typed thin wrappers over the generated OpenAPI paths.
import type { paths } from "./schema.gen";
import { client } from "./index";

type RequestOptions = { headers?: HeadersInit };

export type LLMSettingsOut =
  paths["/me/llm"]["get"]["responses"]["200"]["content"]["application/json"];

export async function getLLMSettings(
  options?: RequestOptions,
): Promise<LLMSettingsOut> {
  const { data, error } = await client.GET("/me/llm", {
    cache: "no-store",
    headers: options?.headers,
  });
  if (error || !data) throw new Error("llm settings fetch failed");
  return data;
}

export async function putLLMCredential(
  provider: string,
  apiKey: string,
): Promise<void> {
  const { error, response } = await client.PUT("/me/llm/credentials/{provider}", {
    params: { path: { provider } },
    body: { api_key: apiKey },
  });
  if (error) {
    throw new Error(
      response?.status === 400 ? "invalid_key" : "credential save failed",
    );
  }
}

export async function deleteLLMCredential(provider: string): Promise<void> {
  const { error } = await client.DELETE("/me/llm/credentials/{provider}", {
    params: { path: { provider } },
  });
  if (error) throw new Error("credential delete failed");
}

export async function putLLMDefault(
  provider: string,
  model: string,
): Promise<void> {
  const { error } = await client.PUT("/me/llm/default", {
    body: { provider, model },
  });
  if (error) throw new Error("default save failed");
}
