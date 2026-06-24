import asyncio
import logging

from app.tasks import WorkerSettings, process_snapshot


def test_process_snapshot_is_a_noop_and_logs(caplog):
    with caplog.at_level(logging.INFO):
        asyncio.run(process_snapshot({}, "abc-123"))
    assert "abc-123" in caplog.text


def test_worker_registers_process_snapshot():
    assert process_snapshot in WorkerSettings.functions
