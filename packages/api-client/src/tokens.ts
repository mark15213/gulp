// PAT management helpers (spec 2026-07-16). Same pattern as llm.ts:
// typed thin wrappers over the generated OpenAPI paths.
import type { paths } from "./schema.gen";
import { client } from "./index";

type RequestOptions = { headers?: HeadersInit };

export type TokenOut =
  paths["/me/tokens"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type TokenCreatedOut =
  paths["/me/tokens"]["post"]["responses"]["201"]["content"]["application/json"];

export async function getTokens(options?: RequestOptions): Promise<TokenOut[]> {
  const { data, error } = await client.GET("/me/tokens", {
    cache: "no-store",
    headers: options?.headers,
  });
  if (error || !data) throw new Error("tokens fetch failed");
  return data;
}

export async function createToken(name: string): Promise<TokenCreatedOut> {
  const { data, error } = await client.POST("/me/tokens", { body: { name } });
  if (error || !data) throw new Error("token create failed");
  return data;
}

export async function revokeToken(id: string): Promise<void> {
  const { error } = await client.DELETE("/me/tokens/{token_id}", {
    params: { path: { token_id: id } },
  });
  if (error) throw new Error("token revoke failed");
}
