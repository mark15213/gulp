import uuid

from gulp_shared.models.pack_message import ChatRole, PackMessage


def test_pack_message_fields() -> None:
    block_id = uuid.uuid4()
    m = PackMessage(
        snapshot_id=uuid.uuid4(),
        role=ChatRole.user,
        content="hi",
        block_refs=[str(block_id)],
    )
    assert m.role is ChatRole.user
    assert m.content == "hi"
    assert m.block_refs == [str(block_id)]
    assert PackMessage.__tablename__ == "pack_messages"
