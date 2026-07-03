"""Assemble downloadable job archives (digest / cards) an external agent can run."""

import hashlib
import json

from app.export.archive import write_zip
from app.export.manifest import build_manifest
from app.export.templates import (
    cards_claude_md,
    cards_prompt_md,
    cards_schema,
    claude_md,
    pack_schema,
    prompt_md,
)
from app.pipeline.normdoc import NormDoc


def build_job_archive(
    *, snapshot_id: str, owner_id: str, normdoc: NormDoc, created_at: str
) -> bytes:
    norm_doc_bytes = normdoc.model_dump_json(indent=2).encode()
    manifest = build_manifest(
        snapshot_id=snapshot_id,
        owner_id=owner_id,
        input_sha256=hashlib.sha256(norm_doc_bytes).hexdigest(),
        created_at=created_at,
    )
    files = {
        "CLAUDE.md": claude_md().encode(),
        "prompt.md": prompt_md().encode(),
        "manifest.json": json.dumps(manifest, indent=2).encode(),
        "input/norm_doc.json": norm_doc_bytes,
        "schema/pack.schema.json": json.dumps(pack_schema(), indent=2).encode(),
        "schema/cards.schema.json": json.dumps(cards_schema(), indent=2).encode(),
        "result/HOWTO.txt": b"Write pack.json here, matching ../schema/pack.schema.json.\n",
    }
    return write_zip(files)


def build_cards_job_archive(
    *,
    snapshot_id: str,
    owner_id: str,
    pack_text: str,
    conversation_text: str,
    created_at: str,
) -> bytes:
    """A card-generation job: the rendered pack (+ conversation) an external
    agent turns into `result/cards.json` (the CardsPayload import contract)."""
    input_blob = f"{pack_text}\n\n{conversation_text}".encode()
    manifest = build_manifest(
        job_kind="cards",
        snapshot_id=snapshot_id,
        owner_id=owner_id,
        input_sha256=hashlib.sha256(input_blob).hexdigest(),
        created_at=created_at,
    )
    files = {
        "CLAUDE.md": cards_claude_md().encode(),
        "prompt.md": cards_prompt_md().encode(),
        "manifest.json": json.dumps(manifest, indent=2).encode(),
        "input/pack.md": pack_text.encode(),
        "schema/cards.schema.json": json.dumps(cards_schema(), indent=2).encode(),
        "result/HOWTO.txt": b'Write cards.json here as {"cards": [...]}, matching '
        b"../schema/cards.schema.json.\n",
    }
    if conversation_text.strip():
        files["input/conversation.md"] = conversation_text.encode()
    return write_zip(files)
