"""Editing, confirming, adding and deleting facts, against the real database."""

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest

from engine.db import Database
from engine.errors import ApiError
from engine.profile import service
from engine.profile.models import MAX_ROWS
from tests.db import fetch, upgrade
from tests.profile_seed import Seeded, seed_profile

USER = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")
OTHER = uuid.UUID("9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d")


@pytest.fixture
async def database(db_url: str) -> AsyncIterator[Database]:
    await upgrade(db_url)
    db = Database(db_url)
    yield db
    await db.dispose()


async def version(db: Database, user: uuid.UUID = USER) -> int:
    return (await service.get_profile(user_id=user, database=db)).version


async def status_of(url: str, table: str, row_id: uuid.UUID) -> str:
    rows = await fetch(url, f"select status from engine.{table} where id = '{row_id}'")  # noqa: S608
    return str(rows[0]["status"])


async def expect(code: int, error_code: str, call: object) -> None:
    with pytest.raises(ApiError) as caught:
        await call  # type: ignore[misc]
    assert (caught.value.status, caught.value.code) == (code, error_code)


async def test_a_real_change_marks_the_fact_edited_and_bumps_the_version(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    item = await service.patch_item(
        user_id=USER,
        kind="experience",
        item_id=str(seeded.experience_ids[0]),
        body={"role": "Principal Engineer", "isCurrent": True},
        database=database,
    )
    assert (item.role, item.is_current, item.status) == (
        "Principal Engineer",
        True,
        "edited",
    )
    assert item.company == "Northwind"  # untouched fields keep their values
    assert await version(database) == 2


async def test_a_patch_that_changes_nothing_is_a_no_op(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    item = await service.patch_item(
        user_id=USER,
        kind="skill",
        item_id=str(seeded.skill_ids[0]),
        body={"name": "Flutter"},
        database=database,
    )
    assert item.status == "extracted"
    assert await version(database) == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"nope": 1},
        {"role": ""},
        {"role": "x" * 201},
        {"start": "March 2020"},
        {"bullets": ["b"] * 21},
    ],
)
async def test_bad_bodies_are_refused_without_echoing_them(
    database: Database, db_url: str, body: dict[str, object]
) -> None:
    seeded = await seed_profile(db_url, USER)
    with pytest.raises(ApiError) as caught:
        await service.patch_item(
            user_id=USER,
            kind="experience",
            item_id=str(seeded.experience_ids[0]),
            body=body,
            database=database,
        )
    assert (caught.value.status, caught.value.code) == (422, "validation_failed")
    assert "xxx" not in caught.value.message
    assert await version(database) == 1


async def test_confirm_moves_extracted_to_confirmed_once(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    first = await service.confirm_item(
        user_id=USER, kind="skill", item_id=str(seeded.skill_ids[0]), database=database
    )
    assert first.status == "confirmed"
    assert await version(database) == 2
    again = await service.confirm_item(
        user_id=USER, kind="skill", item_id=str(seeded.skill_ids[0]), database=database
    )
    assert again.status == "confirmed"
    assert await version(database) == 2  # no change, no bump


async def test_confirming_an_edited_fact_leaves_it_edited(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    await service.patch_item(
        user_id=USER,
        kind="skill",
        item_id=str(seeded.skill_ids[0]),
        body={"name": "Flutter 3"},
        database=database,
    )
    item = await service.confirm_item(
        user_id=USER, kind="skill", item_id=str(seeded.skill_ids[0]), database=database
    )
    assert item.status == "edited"
    assert await version(database) == 2


async def test_delete_removes_the_row_and_unlinks_achievements(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    await service.delete_item(
        user_id=USER,
        kind="experience",
        item_id=str(seeded.experience_ids[0]),
        database=database,
    )
    draft = await service.get_profile(user_id=USER, database=database)
    assert [e.company for e in draft.experiences] == ["Brightside"]
    assert draft.achievements[0].text == "Cut load time"
    assert draft.achievements[0].experience_id is None
    assert draft.version == 2


async def test_confirm_all_confirms_every_extracted_row_once(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    await service.patch_item(
        user_id=USER,
        kind="project",
        item_id=str(seeded.project_ids[0]),
        body={"name": "Side app 2"},
        database=database,
    )  # one edited row, version 2
    done = await service.confirm_all(user_id=USER, database=database)
    assert done == {
        "confirmed": 6,
        "version": 3,
    }  # 2 jobs, 2 skills, 1 achievement, 1 education
    assert await status_of(db_url, "project", seeded.project_ids[0]) == "edited"
    again = await service.confirm_all(user_id=USER, database=database)
    assert again == {"confirmed": 0, "version": 3}


async def test_add_creates_an_edited_row_after_the_last_one(
    database: Database, db_url: str
) -> None:
    await seed_profile(db_url, USER)
    item = await service.add_item(
        user_id=USER, kind="skill", body={"name": "Kotlin"}, database=database
    )
    assert item.status == "edited"
    draft = await service.get_profile(user_id=USER, database=database)
    assert [s.name for s in draft.skills] == ["Flutter", "Dart", "Kotlin"]
    assert draft.version == 2


async def test_the_per_kind_limit_is_enforced(
    database: Database, db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_profile(db_url, USER)
    monkeypatch.setitem(MAX_ROWS, "skill", 3)
    await service.add_item(
        user_id=USER, kind="skill", body={"name": "Kotlin"}, database=database
    )
    await expect(
        422,
        "limit_reached",
        service.add_item(
            user_id=USER, kind="skill", body={"name": "Swift"}, database=database
        ),
    )
    assert await version(database) == 2


async def test_a_duplicate_skill_is_refused_on_add_and_on_rename(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    await expect(
        409,
        "already_exists",
        service.add_item(
            user_id=USER, kind="skill", body={"name": "flutter"}, database=database
        ),
    )
    await expect(
        409,
        "already_exists",
        service.patch_item(
            user_id=USER,
            kind="skill",
            item_id=str(seeded.skill_ids[1]),
            body={"name": "FLUTTER"},
            database=database,
        ),
    )
    assert await version(database) == 1


async def test_an_achievement_may_link_only_to_its_own_profiles_experience(
    database: Database, db_url: str
) -> None:
    mine = await seed_profile(db_url, USER)
    theirs = await seed_profile(db_url, OTHER)
    await expect(
        422,
        "validation_failed",
        service.add_item(
            user_id=USER,
            kind="achievement",
            body={"text": "x", "experienceId": str(theirs.experience_ids[0])},
            database=database,
        ),
    )
    ok = await service.add_item(
        user_id=USER,
        kind="achievement",
        body={"text": "Shipped", "experienceId": str(mine.experience_ids[1])},
        database=database,
    )
    assert ok.experience_id == mine.experience_ids[1]
    moved = await service.patch_item(
        user_id=USER,
        kind="achievement",
        item_id=str(mine.achievement_ids[0]),
        body={"experienceId": None},
        database=database,
    )
    assert moved.experience_id is None


async def test_the_profile_text_can_be_changed(database: Database, db_url: str) -> None:
    await seed_profile(db_url, USER)
    draft = await service.patch_profile(
        user_id=USER,
        body={"headline": "Mobile engineer", "summary": "Ships apps."},
        database=database,
    )
    assert (draft.headline, draft.summary, draft.version) == (
        "Mobile engineer",
        "Ships apps.",
        2,
    )
    same = await service.patch_profile(
        user_id=USER, body={"headline": "Mobile engineer"}, database=database
    )
    assert same.version == 2
    await expect(
        422,
        "validation_failed",
        service.patch_profile(user_id=USER, body={}, database=database),
    )


async def test_nobody_else_can_touch_a_users_facts(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    await seed_profile(db_url, OTHER)
    target = str(seeded.skill_ids[0])
    for call in (
        service.patch_item(
            user_id=OTHER,
            kind="skill",
            item_id=target,
            body={"name": "Hacked"},
            database=database,
        ),
        service.confirm_item(
            user_id=OTHER, kind="skill", item_id=target, database=database
        ),
        service.delete_item(
            user_id=OTHER, kind="skill", item_id=target, database=database
        ),
    ):
        await expect(404, "not_found", call)
    assert await version(database) == 1
    assert await status_of(db_url, "skill", seeded.skill_ids[0]) == "extracted"
    assert (await service.confirm_all(user_id=OTHER, database=database))[
        "confirmed"
    ] == 7
    assert await status_of(db_url, "skill", seeded.skill_ids[0]) == "extracted"


async def test_an_item_of_an_older_draft_and_bad_ids_and_kinds_are_not_found(
    database: Database, db_url: str
) -> None:
    old: Seeded = await seed_profile(db_url, USER, created_at="2026-11-01T00:00:00Z")
    await seed_profile(db_url, USER, created_at="2026-11-05T00:00:00Z")
    await expect(
        404,
        "not_found",
        service.confirm_item(
            user_id=USER, kind="skill", item_id=str(old.skill_ids[0]), database=database
        ),
    )
    for kind, item_id in (
        ("skill", "nope"),
        ("skill", str(uuid.uuid4())),
        ("job", str(uuid.uuid4())),
    ):
        await expect(
            404,
            "not_found",
            service.delete_item(
                user_id=USER, kind=kind, item_id=item_id, database=database
            ),
        )


async def test_no_draft_means_not_found_for_every_action(database: Database) -> None:
    await expect(404, "not_found", service.confirm_all(user_id=USER, database=database))
    await expect(
        404,
        "not_found",
        service.add_item(
            user_id=USER, kind="skill", body={"name": "A"}, database=database
        ),
    )


# ---- concurrency and the remaining rules (review findings F-85, F-86, F-88) -------


async def test_concurrent_edits_to_different_fields_are_both_kept(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    target = str(seeded.experience_ids[0])
    await asyncio.gather(
        service.patch_item(
            user_id=USER,
            kind="experience",
            item_id=target,
            body={"company": "Acme"},
            database=database,
        ),
        service.patch_item(
            user_id=USER,
            kind="experience",
            item_id=target,
            body={"role": "Principal"},
            database=database,
        ),
    )
    draft = await service.get_profile(user_id=USER, database=database)
    first = draft.experiences[0]
    assert (first.company, first.role) == ("Acme", "Principal")
    assert draft.version == 3  # two real changes, one bump each


async def test_a_confirm_racing_an_edit_never_hides_the_edit(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    target = str(seeded.skill_ids[0])
    await asyncio.gather(
        service.confirm_item(
            user_id=USER, kind="skill", item_id=target, database=database
        ),
        service.patch_item(
            user_id=USER,
            kind="skill",
            item_id=target,
            body={"name": "Flutter 3"},
            database=database,
        ),
    )
    assert await status_of(db_url, "skill", seeded.skill_ids[0]) == "edited"


async def test_two_concurrent_adds_of_one_skill_make_one_row(
    database: Database, db_url: str
) -> None:
    await seed_profile(db_url, USER)
    results = await asyncio.gather(
        service.add_item(
            user_id=USER, kind="skill", body={"name": "Rust"}, database=database
        ),
        service.add_item(
            user_id=USER, kind="skill", body={"name": "rust"}, database=database
        ),
        return_exceptions=True,
    )
    errors = [r for r in results if isinstance(r, ApiError)]
    assert len(errors) == 1 and errors[0].code == "already_exists"
    draft = await service.get_profile(user_id=USER, database=database)
    assert [s.name.lower() for s in draft.skills].count("rust") == 1


async def test_concurrent_adds_cannot_pass_the_limit(
    database: Database, db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_profile(db_url, USER)
    monkeypatch.setitem(MAX_ROWS, "skill", 3)  # two exist
    results = await asyncio.gather(
        service.add_item(
            user_id=USER, kind="skill", body={"name": "A1"}, database=database
        ),
        service.add_item(
            user_id=USER, kind="skill", body={"name": "B2"}, database=database
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(r, ApiError) for r in results) == 1
    draft = await service.get_profile(user_id=USER, database=database)
    assert len(draft.skills) == 3


async def test_a_patch_racing_a_delete_is_never_a_server_error(
    database: Database, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER)
    target = str(seeded.skill_ids[0])
    results = await asyncio.gather(
        service.patch_item(
            user_id=USER,
            kind="skill",
            item_id=target,
            body={"name": "Zig"},
            database=database,
        ),
        service.delete_item(
            user_id=USER, kind="skill", item_id=target, database=database
        ),
        return_exceptions=True,
    )
    for result in results:
        assert not isinstance(result, Exception) or (
            isinstance(result, ApiError) and result.code == "not_found"
        )


async def test_the_duplicate_check_folds_case_the_same_way_both_ways(
    database: Database, db_url: str
) -> None:
    await seed_profile(db_url, USER)
    await service.add_item(
        user_id=USER, kind="skill", body={"name": "Straße"}, database=database
    )
    await expect(
        409,
        "already_exists",
        service.add_item(
            user_id=USER, kind="skill", body={"name": "STRASSE"}, database=database
        ),
    )


async def test_an_older_drafts_items_cannot_be_patched_or_deleted(
    database: Database, db_url: str
) -> None:
    old = await seed_profile(db_url, USER, created_at="2026-11-01T00:00:00Z")
    await seed_profile(db_url, USER, created_at="2026-11-05T00:00:00Z")
    target = str(old.skill_ids[0])
    await expect(
        404,
        "not_found",
        service.patch_item(
            user_id=USER,
            kind="skill",
            item_id=target,
            body={"name": "X"},
            database=database,
        ),
    )
    await expect(
        404,
        "not_found",
        service.delete_item(
            user_id=USER, kind="skill", item_id=target, database=database
        ),
    )


async def test_patching_an_achievement_link_to_a_foreign_experience_is_refused(
    database: Database, db_url: str
) -> None:
    mine = await seed_profile(db_url, USER)
    theirs = await seed_profile(db_url, OTHER)
    await expect(
        422,
        "validation_failed",
        service.patch_item(
            user_id=USER,
            kind="achievement",
            item_id=str(mine.achievement_ids[0]),
            body={"experienceId": str(theirs.experience_ids[0])},
            database=database,
        ),
    )


@pytest.mark.parametrize(
    ("kind", "body"),
    [
        ("experience", {"company": "C", "role": "R"}),
        ("achievement", {"text": "T"}),
        ("project", {"name": "P"}),
        ("education", {"institution": "I"}),
    ],
)
async def test_every_kind_has_its_limit(
    database: Database,
    db_url: str,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    body: dict[str, str],
) -> None:
    await seed_profile(db_url, USER)
    monkeypatch.setitem(MAX_ROWS, kind, 1)  # one of each exists already
    await expect(
        422,
        "limit_reached",
        service.add_item(user_id=USER, kind=kind, body=body, database=database),
    )
