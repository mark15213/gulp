"""Concept + edges + typed links — the knowledge graph spine (docs/02 §4.6)."""

import enum
import uuid

from sqlalchemy import JSON, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class ConceptType(enum.StrEnum):
    idea = "idea"
    term = "term"
    person = "person"
    org = "org"


class ConceptRelation(enum.StrEnum):
    related = "related"
    part_of = "part_of"
    contrasts = "contrasts"
    causes = "causes"
    example_of = "example_of"


class Concept(TimestampedBase, Base):
    __tablename__ = "concepts"

    concept_type: Mapped[ConceptType] = mapped_column(Enum(ConceptType, name="concept_type"))
    name: Mapped[str] = mapped_column(String, index=True)
    aliases: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    definition: Mapped[str | None] = mapped_column(Text, default=None)
    # Deferred: mastery rollup — added by S5.


class ConceptEdge(TimestampedBase, Base):
    __tablename__ = "concept_edges"

    from_concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    to_concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    relation: Mapped[ConceptRelation] = mapped_column(
        Enum(ConceptRelation, name="concept_relation")
    )
    weight: Mapped[float | None] = mapped_column(Float, default=None)


class CardConcept(TimestampedBase, Base):
    __tablename__ = "card_concepts"

    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cards.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    role: Mapped[str | None] = mapped_column(String, default=None)


class SourceConcept(TimestampedBase, Base):
    __tablename__ = "source_concepts"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    role: Mapped[str | None] = mapped_column(String, default=None)
