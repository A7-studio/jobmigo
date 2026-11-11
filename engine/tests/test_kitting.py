"""Writing the kit for a job and a track, against the real test database."""

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest

from engine.ai.errors import AiOutputInvalidError
from engine.ai.provider import AiRequest, AiResponse
from engine.db import Database
from engine.errors import ApiError
from engine.jobs.kitting import MAX_VERSIONS, generate_kit, list_kits
from tests.db import fetch, upgrade
from tests.profile_seed import Seeded, seed_profile
from tests.test_ai_gateway import ENV as CHEAP_ENV

ENV = {**CHEAP_ENV, "AI_STRONG_MODEL": "deepseek/model-b", "AI_STRONG_PRICE": "3,6"}
USER = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")
OTHER = uuid.UUID("9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d")
POSTING = "We need a Flutter engineer to build mobile apps."


@pytest.fixture
async def database(db_url: str) -> AsyncIterator[Database]:
    await upgrade(db_url)
    db = Database(db_url)
    yield db
    await db.dispose()


class Kit:
    """Writes each document by reading the request, citing real labels, and counting."""

    name = "kit"

    def __init__(self, *, bad_letter: bool = False) -> None:
        self.requests: list[AiRequest] = []
        self.bad_letter = bad_letter

    @staticmethod
    def labels(request: AiRequest) -> list[str]:
        return re.findall(r"^([A-Z]\d+):", request.user, flags=re.MULTILINE)

    def count(self, word: str) -> int:
        return sum(1 for r in self.requests if word in r.system)

    async def complete(self, request: AiRequest) -> AiResponse:
        self.requests.append(request)
        labels = self.labels(request)
        first = labels[0] if labels else "Z9"
        if "tailored CV" in request.system:
            body: dict[str, object] = {
                "summary": {"text": "Flutter engineer.", "sources": [first]},
                "entries": [
                    {
                        "fact": first,
                        "bullets": [{"text": "Built apps.", "sources": [first]}],
                    }
                ],
                "skills": [label for label in labels if label.startswith("S")],
            }
        elif "draft answers" in request.system or "answers to the application" in (
            request.system
        ):
            count = len(re.findall(r"^\d+\. ", request.user, flags=re.MULTILINE))
            body = {
                "answers": [
                    {"index": i, "text": f"Answer {i}.", "sources": [first]}
                    for i in range(1, count + 1)
                ]
            }
        elif self.bad_letter and "cover letter" in request.system:
            return AiResponse("not json", 5, 5)
        else:
            body = {"paragraphs": [{"text": "I build apps.", "sources": [first]}]}
        return AiResponse(json.dumps(body), 30, 20)


async def run(url: str, query: str, *args: object) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()


async def add_job(
    url: str,
    user: uuid.UUID = USER,
    kind: str = "job",
    text: str = POSTING,
    company: str = "Acme",
) -> str:
    job = uuid.uuid4()
    await run(
        url,
        "insert into engine.job (id, user_id, company, title, location, dedupe_key,"
        " description, kind) values ($1, $2, $3, 'Flutter Engineer', 'Remote', $4,"
        " $5, $6)",
        job,
        user,
        company,
        f"k-{job}",
        text,
        kind,
    )
    return str(job)


async def add_track(
    url: str, user: uuid.UUID = USER, name: str = "Mobile", kind: str = "job"
) -> str:
    track = uuid.uuid4()
    await run(
        url,
        "insert into engine.track (id, user_id, name, kind) values ($1, $2, $3, $4)",
        track,
        user,
        name,
        kind,
    )
    return str(track)


async def confirmed_profile(url: str, user: uuid.UUID = USER) -> Seeded:
    seeded = await seed_profile(url, user)
    await run(
        url,
        "update engine.skill set status = 'confirmed' where id = any($1)",
        seeded.skill_ids[:1],
    )
    await run(
        url,
        "update engine.experience set status = 'confirmed' where id = any($1)",
        seeded.experience_ids[:1],
    )
    return seeded


async def kit(
    database: Database,
    job: str,
    track: str,
    provider: Kit,
    user: uuid.UUID = USER,
    questions: list[str] | None = None,
) -> list[dict[str, object]]:
    body: dict[str, object] = {"trackId": track}
    if questions is not None:
        body["questions"] = questions
    out = await generate_kit(
        user_id=user,
        job_id=job,
        body=body,
        database=database,
        env=ENV,
        provider=provider,
    )
    return [o.model_dump(by_alias=True, mode="json") for o in out]


async def test_a_job_kit_is_a_cv_and_a_letter_saved_as_version_one(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    provider = Kit()
    docs = await kit(database, job, track, provider)
    assert [d["docType"] for d in docs] == ["cv", "letter"]
    assert [d["version"] for d in docs] == [1, 1]
    assert all(d["stale"] is False for d in docs)
    assert all(d["factCheck"]["flagged"] == 0 for d in docs)  # type: ignore[index]
    assert docs[0]["trackName"] == "Mobile"
    assert provider.count("tailored CV") == 1 and provider.count("cover letter") == 1
    rows = await fetch(
        db_url,
        "select workflow, prompt_version from engine.usage_event"
        " where user_id = $1 order by prompt_version",
        USER,
    )
    assert [(r["workflow"], r["prompt_version"]) for r in rows] == [
        ("tailor", "kit-cv-1"),
        ("tailor", "kit-letter-1"),
    ]


async def test_the_same_inputs_again_make_no_model_call_and_no_new_version(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    provider = Kit()
    first = await kit(database, job, track, provider)
    again = await kit(database, job, track, provider)
    assert len(provider.requests) == 2
    assert [d["id"] for d in again] == [d["id"] for d in first]


async def test_questions_add_an_answers_document_and_keep_the_others(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    provider = Kit()
    await kit(database, job, track, provider)
    docs = await kit(database, job, track, provider, questions=["Why us?", "Rate?"])
    assert [d["docType"] for d in docs] == ["cv", "letter", "answers"]
    assert [d["version"] for d in docs] == [1, 1, 1]
    assert len(provider.requests) == 3  # cv and letter were kept
    answers = docs[2]["content"]["answers"]  # type: ignore[index]
    assert [a["question"] for a in answers] == ["Why us?", "Rate?"]
    # new questions make a new answers version only
    docs = await kit(
        database, job, track, provider, questions=["Why us?", "Start date?"]
    )
    assert [d["version"] for d in docs] == [1, 1, 2]


async def test_a_changed_posting_makes_new_versions_and_keeps_the_old(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    provider = Kit()
    await kit(database, job, track, provider)
    await run(
        db_url,
        "update engine.job set description = 'Another posting about Dart.'"
        " where id = $1",
        uuid.UUID(job),
    )
    docs = await kit(database, job, track, provider)
    assert [d["version"] for d in docs] == [2, 2]
    every = await list_kits(user_id=USER, job_id=job, track_id=track, database=database)
    assert sorted((v.doc_type, v.version) for v in every) == [
        ("cv", 1),
        ("cv", 2),
        ("letter", 1),
        ("letter", 2),
    ]


async def test_a_gig_gets_a_proposal_not_a_letter(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url, kind="gig")
    track = await add_track(db_url, kind="gig", name="Gigs")
    docs = await kit(database, job, track, Kit())
    assert [d["docType"] for d in docs] == ["cv", "proposal"]


async def test_a_track_of_another_type_is_refused_before_any_model_call(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url, kind="gig")
    provider = Kit()
    with pytest.raises(ApiError) as caught:
        await kit(database, job, track, provider)
    assert caught.value.code == "wrong_type"
    assert provider.requests == []


async def test_only_confirmed_facts_reach_the_model(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    provider = Kit()
    await kit(database, job, track, provider)
    sent = provider.requests[0].user
    assert "Flutter" in sent  # the confirmed skill
    assert "Dart" not in sent  # an extracted skill is a guess
    assert "Brightside" not in sent  # an extracted experience


async def test_no_confirmed_facts_is_refused(db_url: str, database: Database) -> None:
    await seed_profile(db_url, USER)  # everything is still `extracted`
    job, track = await add_job(db_url), await add_track(db_url)
    provider = Kit()
    with pytest.raises(ApiError) as caught:
        await kit(database, job, track, provider)
    assert caught.value.code == "no_confirmed_profile"
    assert provider.requests == []


async def test_another_users_job_and_track_are_never_used(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    await confirmed_profile(db_url, OTHER)
    mine, theirs = await add_job(db_url), await add_job(db_url, OTHER, company="Z")
    my_track, their_track = await add_track(db_url), await add_track(db_url, OTHER)
    provider = Kit()
    for job, track in ((theirs, my_track), (mine, their_track)):
        with pytest.raises(ApiError) as caught:
            await kit(database, job, track, provider)
        assert caught.value.status == 404
    assert provider.requests == []
    await kit(database, theirs, their_track, Kit(), user=OTHER)
    assert (
        await list_kits(user_id=USER, job_id=mine, track_id=None, database=database)
        == []
    )
    with pytest.raises(ApiError):
        await list_kits(user_id=USER, job_id=theirs, track_id=None, database=database)


async def test_if_one_document_fails_none_is_saved_and_both_calls_are_recorded(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    with pytest.raises(AiOutputInvalidError):
        await kit(database, job, track, Kit(bad_letter=True))
    assert await fetch(db_url, "select 1 from engine.kit_version") == []
    outcomes = await fetch(
        db_url,
        "select outcome from engine.usage_event where user_id = $1 order by created_at",
        USER,
    )
    assert [r["outcome"] for r in outcomes] == ["ok", "rejected", "rejected"]


async def test_only_the_newest_versions_are_kept(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    provider = Kit()
    for n in range(MAX_VERSIONS + 2):
        await run(
            db_url,
            "update engine.job set description = $2 where id = $1",
            uuid.UUID(job),
            f"{POSTING} Round {n}.",
        )
        await kit(database, job, track, provider)
    versions = await fetch(
        db_url,
        "select version from engine.kit_version where doc_type = 'cv' order by version",
    )
    assert [r["version"] for r in versions] == list(range(3, MAX_VERSIONS + 3))


async def test_the_list_gives_the_latest_of_each_document_or_every_version_of_a_track(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    first, second = await add_track(db_url), await add_track(db_url, name="Other")
    provider = Kit()
    await kit(database, job, first, provider)
    await kit(database, job, second, provider)
    await run(
        db_url,
        "update engine.job set description = 'Changed text.' where id = $1",
        uuid.UUID(job),
    )
    await kit(database, job, first, provider)
    latest = await list_kits(user_id=USER, job_id=job, track_id=None, database=database)
    assert [(v.track_name, v.doc_type, v.version) for v in latest] == [
        ("Mobile", "cv", 2),
        ("Mobile", "letter", 2),
        ("Other", "cv", 1),
        ("Other", "letter", 1),
    ]
    one = await list_kits(user_id=USER, job_id=job, track_id=first, database=database)
    assert len(one) == 4


async def test_versions_for_a_track_of_another_type_are_hidden_not_deleted(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    await kit(database, job, track, Kit())
    await run(
        db_url, "update engine.job set kind = 'gig' where id = $1", uuid.UUID(job)
    )
    assert (
        await list_kits(user_id=USER, job_id=job, track_id=None, database=database)
        == []
    )
    await run(
        db_url, "update engine.job set kind = 'job' where id = $1", uuid.UUID(job)
    )
    back = await list_kits(user_id=USER, job_id=job, track_id=None, database=database)
    assert len(back) == 2


async def test_a_newer_profile_makes_an_old_version_stale(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    await kit(database, job, track, Kit())
    newer = await seed_profile(db_url, USER, created_at="2026-11-10T00:00:00Z")
    await run(
        db_url,
        "update engine.skill set status = 'confirmed' where id = $1",
        newer.skill_ids[0],
    )
    listed = await list_kits(user_id=USER, job_id=job, track_id=None, database=database)
    assert [v.stale for v in listed] == [True, True]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"trackId": "nope"},
        {"trackId": str(uuid.uuid4()), "extra": 1},
        {"trackId": str(uuid.uuid4()), "questions": "why"},
        {"trackId": str(uuid.uuid4()), "questions": ["q"] * 6},
        {"trackId": str(uuid.uuid4()), "questions": ["x" * 501]},
        {"trackId": str(uuid.uuid4()), "questions": [1]},
    ],
)
async def test_a_bad_request_is_refused(
    db_url: str, database: Database, body: dict[str, object]
) -> None:
    job = await add_job(db_url)
    with pytest.raises(ApiError) as caught:
        await generate_kit(
            user_id=USER, job_id=job, body=body, database=database, env=ENV
        )
    assert caught.value.status == 422


async def test_blank_questions_are_dropped(db_url: str, database: Database) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    docs = await kit(database, job, track, Kit(), questions=["  ", "Why us?", ""])
    assert [a["question"] for a in docs[2]["content"]["answers"]] == [  # type: ignore[index]
        "Why us?"
    ]
    none = await kit(database, job, track, Kit(), questions=["", "  "])
    assert [d["docType"] for d in none] == ["cv", "letter"]


async def test_a_malformed_job_id_is_not_found(database: Database) -> None:
    with pytest.raises(ApiError) as caught:
        await generate_kit(
            user_id=USER,
            job_id="nope",
            body={"trackId": str(uuid.uuid4())},
            database=database,
            env=ENV,
        )
    assert caught.value.status == 404


async def test_nothing_the_person_wrote_or_the_model_said_is_logged(
    db_url: str, database: Database, caplog: pytest.LogCaptureFixture
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    caplog.set_level(logging.DEBUG)
    await kit(
        database,
        job,
        track,
        Kit(),
        questions=["A private question about my salary?"],
    )
    text = " ".join(r.getMessage() + str(r.__dict__) for r in caplog.records)
    for secret in ("private question", "Flutter engineer", "I build apps", "Northwind"):
        assert secret not in text


async def test_identical_requests_at_once_make_one_kit_not_three(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    provider = Kit()
    results = await asyncio.gather(
        *(kit(database, job, track, provider) for _ in range(3))
    )
    assert len(provider.requests) == 2  # one CV and one letter, not six calls
    versions = await fetch(
        db_url,
        "select doc_type, version from engine.kit_version order by doc_type, version",
    )
    assert [(r["doc_type"], r["version"]) for r in versions] == [
        ("cv", 1),
        ("letter", 1),
    ]
    assert len({tuple(d["id"] for d in docs) for docs in results}) == 1


async def kit_edit_bullet(
    database: Database, job: str, doc_id: str, **body: object
) -> dict[str, object]:
    from engine.jobs.kitting import edit_kit

    out = await edit_kit(
        user_id=USER, job_id=job, kit_id=doc_id, body=dict(body), database=database
    )
    return out.model_dump(by_alias=True, mode="json")


async def test_editing_a_statement_makes_the_next_version_and_keeps_the_old(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    cv, _ = await kit(database, job, track, Kit())
    new = await kit_edit_bullet(
        database,
        job,
        str(cv["id"]),
        path="entries.1.bullets.1",
        action="edit",
        text="Built 99 apps.",
    )
    assert (new["docType"], new["version"], new["trackName"]) == ("cv", 2, "Mobile")
    bullet = new["content"]["entries"][0]["bullets"][0]  # type: ignore[index]
    assert (bullet["text"], bullet["edited"]) == ("Built 99 apps.", True)
    assert bullet["flags"] == ["unsupported_number"]
    assert new["factCheck"]["edited"] == ["entries.1.bullets.1"]  # type: ignore[index]
    rows = await fetch(
        db_url,
        "select version, content->'entries'->0->'bullets'->0->>'text' as text,"
        " cache_key from engine.kit_version where doc_type = 'cv' order by version",
    )
    assert [(r["version"], r["text"]) for r in rows] == [
        (1, "Built apps."),
        (2, "Built 99 apps."),
    ]
    assert str(rows[1]["cache_key"]).startswith("edit:")


async def test_only_the_latest_version_can_be_changed(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    cv, _ = await kit(database, job, track, Kit())
    await kit_edit_bullet(
        database, job, str(cv["id"]), path="summary", action="edit", text="New."
    )
    with pytest.raises(ApiError) as caught:
        await kit_edit_bullet(
            database, job, str(cv["id"]), path="summary", action="edit", text="Again."
        )
    assert (caught.value.status, caught.value.code) == (409, "not_latest")


async def test_writing_again_after_an_edit_makes_a_fresh_version_and_keeps_the_edit(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    provider = Kit()
    cv, _ = await kit(database, job, track, provider)
    await kit_edit_bullet(
        database, job, str(cv["id"]), path="summary", action="edit", text="Mine."
    )
    docs = await kit(database, job, track, provider)
    assert [(d["docType"], d["version"]) for d in docs] == [("cv", 3), ("letter", 1)]
    # the same model input is served by the gateway cache, so no new model call is paid
    assert len(provider.requests) == 2


async def test_a_source_the_person_unconfirmed_is_flagged_after_an_edit(
    db_url: str, database: Database
) -> None:
    seeded = await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    cv, _ = await kit(database, job, track, Kit())
    await run(
        db_url,
        "update engine.experience set status = 'extracted' where id = any($1)",
        seeded.experience_ids,
    )
    new = await kit_edit_bullet(
        database, job, str(cv["id"]), path="summary", action="edit", text="Fine."
    )
    bullet = new["content"]["entries"][0]["bullets"][0]  # type: ignore[index]
    assert bullet["flags"] == ["no_source"]
    assert new["factCheck"]["flagged"] >= 1  # type: ignore[index]


async def test_another_users_or_a_hidden_or_made_up_kit_cannot_be_changed(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    await confirmed_profile(db_url, OTHER)
    job, track = await add_job(db_url), await add_track(db_url)
    cv, _ = await kit(database, job, track, Kit())
    from engine.jobs.kitting import edit_kit

    for user, job_id, kit_id in (
        (OTHER, job, str(cv["id"])),
        (USER, job, str(uuid.uuid4())),
        (USER, job, "nope"),
        (USER, "nope", str(cv["id"])),
    ):
        with pytest.raises(ApiError) as caught:
            await edit_kit(
                user_id=user,
                job_id=job_id,
                kit_id=kit_id,
                body={"path": "summary", "action": "edit", "text": "x"},
                database=database,
            )
        assert caught.value.status == 404, (user, job_id, kit_id)
    await run(
        db_url, "update engine.job set kind = 'gig' where id = $1", uuid.UUID(job)
    )
    with pytest.raises(ApiError) as caught:
        await kit_edit_bullet(
            database, job, str(cv["id"]), path="summary", action="edit", text="x"
        )
    assert caught.value.status == 404


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"path": "summary"},
        {"path": "summary", "action": "burn"},
        {"path": "summary", "action": "edit", "text": "x", "extra": 1},
        {"path": "x" * 41, "action": "edit", "text": "x"},
        {"path": "summary", "action": "edit", "text": "x" * 2001},
        {"path": "summary", "action": "edit", "text": 5},
        {"path": "summary", "action": "remove"},
        {"path": "entries.1", "action": "edit", "text": "x"},
    ],
)
async def test_a_bad_edit_request_is_refused_and_changes_nothing(
    db_url: str, database: Database, body: dict[str, object]
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    cv, _ = await kit(database, job, track, Kit())
    with pytest.raises(ApiError) as caught:
        await kit_edit_bullet(database, job, str(cv["id"]), **body)
    assert caught.value.status == 422
    rows = await fetch(
        db_url, "select version from engine.kit_version where doc_type = 'cv'"
    )
    assert [r["version"] for r in rows] == [1]


async def test_concurrent_edits_make_one_version_each_in_order(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job, track = await add_job(db_url), await add_track(db_url)
    cv, _ = await kit(database, job, track, Kit())
    results = await asyncio.gather(
        *(
            kit_edit_bullet(
                database, job, str(cv["id"]), path="summary", action="edit", text="A."
            )
            for _ in range(3)
        ),
        return_exceptions=True,
    )
    made = [r for r in results if isinstance(r, dict)]
    refused = [r for r in results if isinstance(r, ApiError)]
    assert len(made) == 1 and len(refused) == 2
    assert all(r.code == "not_latest" for r in refused)
