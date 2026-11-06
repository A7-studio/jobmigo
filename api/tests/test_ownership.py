import uuid

from sqlalchemy import Text, text, update
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.identity.models import User
from app.platform.ownership import OwnedRepository, owner_scoped


class _TestBase(DeclarativeBase):
    pass


class Note(_TestBase):
    __tablename__ = "scoped_note"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    body: Mapped[str] = mapped_column(Text)


class NoteRepository(OwnedRepository):
    model = Note


async def _setup(session: AsyncSession) -> tuple[User, User, Note, Note]:
    connection = await session.connection()
    await connection.run_sync(lambda conn: Note.__table__.create(conn))
    users = []
    for name in ("a", "b"):
        user = User(auth_subject=f"s_{name}", email=f"{name}@example.com")
        session.add(user)
        users.append(user)
    await session.flush()
    notes = [Note(user_id=u.id, body=f"note of {u.email}") for u in users]
    session.add_all(notes)
    await session.flush()
    return users[0], users[1], notes[0], notes[1]


async def test_user_only_sees_their_own_rows(session: AsyncSession) -> None:
    a, b, note_a, note_b = await _setup(session)
    repo = NoteRepository(session, a)
    assert [n.id for n in await repo.list_all()] == [note_a.id]
    assert await repo.get(note_a.id) is not None
    assert await repo.get(note_b.id) is None


async def test_user_cannot_delete_another_users_row(session: AsyncSession) -> None:
    a, b, note_a, note_b = await _setup(session)
    assert await NoteRepository(session, a).delete(note_b.id) is False
    remaining = await session.scalar(text("SELECT count(*) FROM scoped_note"))
    assert remaining == 2
    assert await NoteRepository(session, a).delete(note_a.id) is True


async def test_user_cannot_update_another_users_row(session: AsyncSession) -> None:
    a, b, note_a, note_b = await _setup(session)
    statement = owner_scoped(
        update(Note).where(Note.id == note_b.id).values(body="hacked"), Note, a
    )
    result = await session.execute(statement)
    assert result.rowcount == 0  # type: ignore[attr-defined]
    body = await session.scalar(
        text("SELECT body FROM scoped_note WHERE id = :i"), {"i": note_b.id}
    )
    assert body == f"note of {b.email}"
