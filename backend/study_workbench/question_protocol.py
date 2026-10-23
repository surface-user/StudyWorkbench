"""Version-one content contract. Validation is separate from import and rendering."""

import re
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

ResourceId = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=500, pattern=r"\S")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("schema_version", mode="before", check_fields=False)
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value


class TextBlock(Contract):
    type: Literal["text"]
    text: Annotated[str, Field(min_length=1, max_length=20000)]


class LatexBlock(Contract):
    type: Literal["latex"]
    tex: Annotated[str, Field(min_length=1, max_length=8000)]
    display: bool = False

    @model_validator(mode="after")
    def bounded_math(self) -> Self:
        if re.search(
            r"\\(?:input|include|includegraphics|openin|openout|read|write|usepackage|"
            r"documentclass|href|url|html\w*|def|newcommand|renewcommand|csname)(?![A-Za-z])",
            self.tex,
            flags=re.IGNORECASE,
        ):
            raise ValueError("External-resource and macro-definition TeX commands are forbidden")
        return self


class ImageBlock(Contract):
    type: Literal["image"]
    attachment_id: ResourceId
    alt: ShortText
    caption: ShortText | None = None


class ChartBlock(Contract):
    type: Literal["chart"]
    attachment_id: ResourceId
    alt: ShortText
    data_attachment_id: ResourceId | None = None


class AttachmentBlock(Contract):
    type: Literal["attachment"]
    attachment_id: ResourceId
    label: ShortText


InlineBlock = Annotated[
    TextBlock | LatexBlock | ImageBlock | ChartBlock | AttachmentBlock, Field(discriminator="type")
]
Cell = Annotated[list[InlineBlock], Field(min_length=1, max_length=20)]


class TableBlock(Contract):
    type: Literal["table"]
    headers: Annotated[list[Cell], Field(min_length=1, max_length=20)]
    rows: Annotated[list[list[Cell]], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def rectangular(self) -> Self:
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Every table row must match the header column count")
        return self


Block = Annotated[
    TextBlock | LatexBlock | ImageBlock | ChartBlock | AttachmentBlock | TableBlock,
    Field(discriminator="type"),
]
Content = Annotated[list[Block], Field(min_length=1, max_length=200)]


class Source(Contract):
    kind: Literal["manual", "imported", "official", "ai_generated"]
    title: ShortText
    verification: Literal["unverified", "human_verified", "rejected"] = "unverified"
    original_resource_id: ResourceId | None = None
    page: Annotated[int, Field(strict=True, ge=1)] | None = None
    url: Annotated[str, Field(max_length=2000, pattern=r"^https://[^\s]+$")] | None = None
    license: ShortText | None = None
    model: ShortText | None = None
    generated_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def provenance(self) -> Self:
        if self.kind == "ai_generated":
            if self.model is None or self.generated_at is None:
                raise ValueError("AI provenance requires model and timezone-aware generated_at")
        elif self.model is not None or self.generated_at is not None:
            raise ValueError("AI provenance must retain ai_generated source kind")
        if self.kind == "official" and self.verification != "human_verified":
            raise ValueError("Unverified material cannot be labelled official")
        return self


class Option(Contract):
    id: ResourceId
    content: Content


class ChoiceAnswer(Contract):
    selected: Annotated[list[ResourceId], Field(min_length=1, max_length=30)]


class BlankAnswer(Contract):
    id: ResourceId
    accepted: Annotated[list[ShortText], Field(min_length=1, max_length=30)]
    normalization: Literal["exact", "trim"]


class FillAnswer(Contract):
    blanks: Annotated[list[BlankAnswer], Field(min_length=1, max_length=30)]


class WrittenAnswer(Contract):
    rubric: Annotated[str, Field(min_length=1, max_length=20000)]
    reference: list[Block] = Field(default_factory=list, max_length=200)


class QuestionDocument(Contract):
    schema_version: Literal[1]
    id: ResourceId
    revision: Annotated[int, Field(strict=True, ge=1)]
    subject: ShortText
    kind: Literal[
        "single_choice",
        "multiple_choice",
        "fill_blank",
        "calculation",
        "proof",
        "subjective",
        "reading_question",
    ]
    response_kind: Literal["single_choice", "multiple_choice", "fill_blank", "subjective"] | None = None
    stem: Content
    options: list[Option] = Field(default_factory=list, max_length=30)
    answer: ChoiceAnswer | FillAnswer | WrittenAnswer
    explanation: Content
    knowledge_points: Annotated[list[ShortText], Field(min_length=1, max_length=100)]
    source: Source
    passage_id: ResourceId | None = None
    parent_question_id: ResourceId | None = None

    @model_validator(mode="after")
    def answer_matches_kind(self) -> Self:
        kind = self.kind
        if kind == "reading_question":
            if self.passage_id is None or self.response_kind is None:
                raise ValueError("Reading questions require passage_id and response_kind")
            kind = self.response_kind
        elif self.response_kind is not None:
            raise ValueError("response_kind is only used by reading_question")
        if self.parent_question_id == self.id:
            raise ValueError("A question cannot be its own parent")
        if kind in {"single_choice", "multiple_choice"}:
            ids = [option.id for option in self.options]
            if len(ids) < 2 or len(ids) != len(set(ids)):
                raise ValueError("Choice questions require at least two uniquely identified options")
            if not isinstance(self.answer, ChoiceAnswer):
                raise ValueError("Choice answer required")
            selected = self.answer.selected
            if len(selected) != len(set(selected)) or not set(selected) <= set(ids):
                raise ValueError("Answer IDs must be unique and reference existing options")
            if kind == "single_choice" and len(selected) != 1:
                raise ValueError("Single choice requires exactly one correct option")
        else:
            if self.options:
                raise ValueError("Non-choice questions cannot carry choice options")
            expected = FillAnswer if kind == "fill_blank" else WrittenAnswer
            if not isinstance(self.answer, expected):
                raise ValueError("Answer structure does not match question kind")
            if isinstance(self.answer, FillAnswer):
                ids = [blank.id for blank in self.answer.blanks]
                if len(ids) != len(set(ids)):
                    raise ValueError("Blank IDs must be unique")
        return self


class Passage(Contract):
    id: ResourceId
    content: Content
    source: Source


class QuestionBundle(Contract):
    """Question/passage references are self-contained; file resolution belongs to M2."""

    schema_version: Literal[1]
    passages: list[Passage] = Field(default_factory=list, max_length=100)
    questions: Annotated[list[QuestionDocument], Field(min_length=1, max_length=1000)]

    @model_validator(mode="after")
    def references(self) -> Self:
        passage_ids = [passage.id for passage in self.passages]
        questions = {question.id: question for question in self.questions}
        if len(passage_ids) != len(set(passage_ids)) or len(questions) != len(self.questions):
            raise ValueError("Question and passage IDs must be unique within their collections")
        for question in self.questions:
            if question.passage_id and question.passage_id not in passage_ids:
                raise ValueError("Unresolved passage reference")
            visited = {question.id}
            parent = question.parent_question_id
            while parent is not None:
                if parent not in questions:
                    raise ValueError("Unresolved parent reference")
                if parent in visited:
                    raise ValueError("Question provenance cannot contain cycles")
                visited.add(parent)
                parent = questions[parent].parent_question_id
        return self
