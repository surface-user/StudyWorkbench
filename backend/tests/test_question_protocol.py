import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError
from study_workbench.content import DEMO
from study_workbench.question_protocol import QuestionBundle, QuestionDocument, WrittenAnswer


def question(kind="single_choice"):
    value = deepcopy(DEMO)
    value["kind"] = kind
    if kind == "multiple_choice":
        value["answer"] = {"selected": ["a", "b"]}
    elif kind == "fill_blank":
        value["options"] = []
        value["answer"] = {"blanks": [{"id": "blank-1", "accepted": ["1/3"], "normalization": "trim"}]}
    elif kind in {"calculation", "proof", "subjective"}:
        value["options"] = []
        value["answer"] = {"rubric": "给出原函数及上下限代入。", "reference": value["explanation"]}
    elif kind == "reading_question":
        value["passage_id"] = "passage-1"
        value["response_kind"] = "single_choice"
    return value


@pytest.mark.parametrize(
    "kind",
    [
        "single_choice",
        "multiple_choice",
        "fill_blank",
        "calculation",
        "proof",
        "subjective",
        "reading_question",
    ],
)
def test_all_question_kinds_round_trip(kind):
    original = question(kind)
    validated = QuestionDocument.model_validate_json(json.dumps(original))
    assert QuestionDocument.model_validate_json(validated.model_dump_json()) == validated
    assert validated.kind == kind
    if kind in {"calculation", "proof", "subjective"}:
        assert isinstance(validated.answer, WrittenAnswer)


def test_rich_content_is_data_not_html_or_paths():
    value = question()
    value["stem"] += [
        {"type": "image", "attachment_id": "figure-1", "alt": "积分面积示意图"},
        {"type": "chart", "attachment_id": "chart-1", "alt": "函数曲线", "data_attachment_id": "data-1"},
        {"type": "attachment", "attachment_id": "source-pdf", "label": "原文附件"},
        {
            "type": "table",
            "headers": [[{"type": "text", "text": "变量"}]],
            "rows": [[[{"type": "latex", "tex": "x=1"}]]],
        },
    ]
    document = QuestionDocument.model_validate(value)
    assert [block.type for block in document.stem] == [
        "text",
        "latex",
        "image",
        "chart",
        "attachment",
        "table",
    ]
    assert document.stem[-1].rows[0][0][0].tex == "x=1"


@pytest.mark.parametrize(
    "block",
    [
        {"type": "html", "html": "<script>alert(1)</script>"},
        {"type": "latex", "tex": r"\input{C:/secret}"},
        {"type": "latex", "tex": r"\write18{command}"},
        {"type": "latex", "tex": r"\includegraphics{https://example.com/x}"},
        {"type": "latex", "tex": r"\newcommand{\x}{\x}"},
        {"type": "image", "attachment_id": "../../private.db", "alt": "invalid"},
        {"type": "attachment", "attachment_id": "file:///C:/secret", "label": "invalid"},
        {"type": "table", "headers": [[{"type": "text", "text": "列"}]], "rows": [[]]},
    ],
)
def test_unsafe_or_malformed_blocks_rejected(block):
    value = question()
    value["stem"] = [block]
    with pytest.raises(ValidationError):
        QuestionDocument.model_validate(value)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda q: q.update(schema_version=2),
        lambda q: q.update(schema_version=True),
        lambda q: q.update(revision=0),
        lambda q: q.update(parent_question_id=q["id"]),
        lambda q: q["options"][1].update(id="a"),
        lambda q: q.update(answer={"selected": ["missing"]}),
        lambda q: q.update(answer={"selected": ["a", "a"]}),
        lambda q: q.update(answer={"selected": ["a", "b"]}),
        lambda q: q.update(answer={"rubric": "not a choice answer"}),
        lambda q: q.update(kind="proof"),
        lambda q: q.update(kind="reading_question"),
        lambda q: q.update(response_kind="single_choice"),
    ],
)
def test_cross_field_invariants(mutation):
    value = question()
    mutation(value)
    with pytest.raises(ValidationError):
        QuestionDocument.model_validate(value)


def test_ai_provenance_remains_distinct_from_official():
    value = question()
    value["source"] = {
        "kind": "ai_generated",
        "title": "AI 演示变式",
        "model": "test-model",
        "generated_at": "2026-10-23T12:00:00+08:00",
    }
    document = QuestionDocument.model_validate(value)
    assert document.source.verification == "unverified"
    for broken in (
        {"kind": "ai_generated", "title": "missing metadata"},
        {**value["source"], "generated_at": "2026-10-23T12:00:00"},
        {**value["source"], "kind": "official", "verification": "human_verified"},
        {"kind": "official", "title": "unverified claim", "verification": "unverified"},
    ):
        with pytest.raises(ValidationError):
            QuestionDocument.model_validate({**value, "source": broken})


def bundle():
    first = question("reading_question")
    second = {**deepcopy(first), "id": "reading-2", "parent_question_id": first["id"]}
    return {
        "schema_version": 1,
        "passages": [
            {
                "id": "passage-1",
                "content": [{"type": "text", "text": "A sample passage."}],
                "source": deepcopy(DEMO["source"]),
            }
        ],
        "questions": [first, second],
    }


def test_reading_bundle_shares_passage_and_retains_parent():
    document = QuestionBundle.model_validate(bundle())
    assert document.questions[0].passage_id == document.questions[1].passage_id
    assert document.questions[1].parent_question_id == document.questions[0].id


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b: b.update(passages=[]),
        lambda b: b["questions"][1].update(id=b["questions"][0]["id"]),
        lambda b: b["questions"][1].update(parent_question_id="absent"),
        lambda b: b["questions"][0].update(parent_question_id=b["questions"][1]["id"]),
    ],
)
def test_bundle_rejects_missing_or_cyclic_references(mutation):
    value = bundle()
    mutation(value)
    with pytest.raises(ValidationError):
        QuestionBundle.model_validate(value)


def test_committed_schema_and_example_are_current():
    root = Path(__file__).resolve().parents[2]
    QuestionDocument.model_validate_json((root / "contracts/question-v1.json").read_text(encoding="utf-8"))
    result = subprocess.run(
        [sys.executable, str(root / "tools/export_question_schema.py"), "--check"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
