"""Snapshot lifecycle domain — single-gate convergence (spec 2026-07-02)."""

from gulp_shared.models.source import SnapshotStatus


def test_status_domain_is_the_single_gate_set():
    assert {s.value for s in SnapshotStatus} == {
        "queued",
        "unprocessed",
        "processing",
        "ready",
        "exported",
        "needs_attention",
    }
