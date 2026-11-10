"""Test data: parsed CVs with drafts, inserted directly."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

import asyncpg


@dataclass
class Seeded:
    cv_id: uuid.UUID
    profile_id: uuid.UUID
    experience_ids: list[uuid.UUID] = field(default_factory=list)
    skill_ids: list[uuid.UUID] = field(default_factory=list)
    achievement_ids: list[uuid.UUID] = field(default_factory=list)
    project_ids: list[uuid.UUID] = field(default_factory=list)
    education_ids: list[uuid.UUID] = field(default_factory=list)


async def seed_profile(
    url: str,
    user: uuid.UUID,
    *,
    created_at: str = "2026-11-01T00:00:00Z",
    status: str = "parsed",
    with_rows: bool = True,
    headline: str = "Flutter engineer",
) -> Seeded:
    cv, profile = uuid.uuid4(), uuid.uuid4()
    seeded = Seeded(cv_id=cv, profile_id=profile)
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(
            "insert into engine.cv_file (id, user_id, storage_key, filename, mime, "
            "size_bytes, extracted_text, parse_status, created_at) "
            "values ($1, $2, $3, 'cv.pdf', 'pdf', 1, 't', $4, $5)",
            cv,
            user,
            f"cv/{cv}",
            status,
            datetime.fromisoformat(created_at),
        )
        if status != "parsed" and not with_rows:
            return seeded
        await connection.execute(
            "insert into engine.profile (id, user_id, source_cv_id, headline) "
            "values ($1, $2, $3, $4)",
            profile,
            user,
            cv,
            headline,
        )
        if not with_rows:
            return seeded
        for position, (company, role) in enumerate(
            [("Northwind", "Senior Engineer"), ("Brightside", "Developer")]
        ):
            eid = uuid.uuid4()
            await connection.execute(
                "insert into engine.experience (id, user_id, profile_id, position, "
                "company, role, bullets) values ($1, $2, $3, $4, $5, $6, '[]'::jsonb)",
                eid,
                user,
                profile,
                position,
                company,
                role,
            )
            seeded.experience_ids.append(eid)
        for position, name in enumerate(["Flutter", "Dart"]):
            sid = uuid.uuid4()
            await connection.execute(
                "insert into engine.skill (id, user_id, profile_id, position, name) "
                "values ($1, $2, $3, $4, $5)",
                sid,
                user,
                profile,
                position,
                name,
            )
            seeded.skill_ids.append(sid)
        aid = uuid.uuid4()
        await connection.execute(
            "insert into engine.achievement (id, user_id, profile_id, position, text, "
            "experience_id) values ($1, $2, $3, 0, 'Cut load time', $4)",
            aid,
            user,
            profile,
            seeded.experience_ids[0],
        )
        seeded.achievement_ids.append(aid)
        pid = uuid.uuid4()
        await connection.execute(
            "insert into engine.project (id, user_id, profile_id, position, name) "
            "values ($1, $2, $3, 0, 'Side app')",
            pid,
            user,
            profile,
        )
        seeded.project_ids.append(pid)
        did = uuid.uuid4()
        await connection.execute(
            "insert into engine.education (id, user_id, profile_id, position, "
            "institution) values ($1, $2, $3, 0, 'University')",
            did,
            user,
            profile,
        )
        seeded.education_ids.append(did)
    finally:
        await connection.close()
    return seeded
