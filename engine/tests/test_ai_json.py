"""Ports of web/tests/ai-json.test.ts (each test names its source case)."""

from pydantic import BaseModel

from engine.ai.json import extract_json, parse_model_output


class Person(BaseModel):
    name: str
    years: float


def test_parses_bare_json() -> None:
    # extractJson: 'parses bare JSON'
    assert extract_json('{"a":1}') == (True, {"a": 1})


def test_parses_a_fenced_block_with_or_without_a_language_tag() -> None:
    # extractJson: 'parses a fenced block with or without a language tag'
    assert extract_json('Here:\n```json\n{"a":2}\n```\nDone') == (True, {"a": 2})
    assert extract_json('```\n{"a":3}\n```') == (True, {"a": 3})


def test_finds_json_inside_surrounding_prose() -> None:
    # extractJson: 'finds JSON inside surrounding prose'
    assert extract_json('Sure! {"a": 4} hope that helps') == (True, {"a": 4})


def test_fails_on_invalid_or_empty_replies() -> None:
    # extractJson: 'fails on invalid or empty replies'
    assert extract_json("no json here")[0] is False
    assert extract_json("   ")[0] is False
    assert extract_json('{"a": ')[0] is False
    assert extract_json('{"a": NaN}')[0] is False


def test_returns_the_validated_value() -> None:
    # parseModelOutput: 'returns the validated value'
    result = parse_model_output('{"name":"Ada","years":3}', Person)
    assert result.ok
    assert result.value == Person(name="Ada", years=3)


def test_reports_invalid_json_without_echoing_the_reply() -> None:
    # parseModelOutput: 'reports invalid JSON without echoing the reply'
    result = parse_model_output("secret-model-text", Person)
    assert not result.ok
    assert "secret-model-text" not in result.reason


def test_reports_schema_mismatches_by_path_and_type_only() -> None:
    # parseModelOutput: 'reports schema mismatches by path and code only'
    result = parse_model_output('{"name":"secret-value","years":"many"}', Person)
    assert not result.ok
    assert "years" in result.reason
    assert "secret-value" not in result.reason
    assert "many" not in result.reason
    assert len(result.reason) < 200


def test_shows_schema_field_names_but_never_model_chosen_keys() -> None:
    # parseModelOutput paths: 'shows schema field names but never model-chosen keys'
    class Skills(BaseModel):
        skills: dict[str, int]

    bad = parse_model_output('{"skills":{"cv secret name":"not a number"}}', Skills)
    assert not bad.ok
    assert "skills.*" in bad.reason
    assert "cv secret name" not in bad.reason


def test_keeps_known_names_through_arrays_and_optional_fields() -> None:
    # parseModelOutput paths: 'keeps known names through arrays and optional fields'
    class Job(BaseModel):
        title: str

    class Note(BaseModel):
        text: str

    class Nested(BaseModel):
        jobs: list[Job]
        note: Note | None = None

    bad = parse_model_output(
        '{"jobs":[{"title":"ok"},{"title":5}],"note":{"text":1}}', Nested
    )
    assert not bad.ok
    assert "jobs.1.title" in bad.reason
    assert "note.text" in bad.reason
