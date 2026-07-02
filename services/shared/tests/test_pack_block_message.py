import uuid

from gulp_shared.models.pack_block_message import ChatRole, PackBlockMessage


def test_pack_block_message_fields() -> None:
    m = PackBlockMessage(block_id=uuid.uuid4(), role=ChatRole.user, content="hi")
    assert m.role is ChatRole.user
    assert m.content == "hi"
    assert PackBlockMessage.__tablename__ == "pack_block_messages"
