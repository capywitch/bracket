from typing import Literal

from pydantic import BaseModel, Field


class Card(BaseModel):
    name: str
    oracle_id: str
    mana_cost: str | None = None
    mana_value: float = 0.0
    type_line: str = ""
    oracle_text: str = ""
    colors: list[str] = Field(default_factory=list)
    color_identity: list[str] = Field(default_factory=list)

class DeckCard(BaseModel):
    card: Card
    quantity: int = 1
    category: str | None = None
    is_commander: bool = False
    is_companion: bool = False

class DeckSource(BaseModel):
    type: Literal["moxfield", "text", "manual"]
    id: str | None = None

class Deck(BaseModel):
    name: str | None = None
    commander: list[DeckCard] = Field(default_factory=list)
    cards: list[DeckCard] = Field(default_factory=list)
    companion: DeckCard | None = None
    source: DeckSource

class EvidenceSource(BaseModel):
    type: Literal["official", "heuristic", "data"]
    rules_version: str | None = None

class Evidence(BaseModel):
    id: str
    type: str
    source: EvidenceSource
    card_or_cards: list[str]
    description: str
    impact: Literal["low", "medium", "high"] | None = None

class Signal(BaseModel):
    id: str
    category: str
    source_type: Literal["official", "heuristic", "data"]
    strength: Literal["low", "medium", "high"]
    evidence: list[Evidence]
    explanation: str
    # Optional bracket-floor override from a signal that already knows a concrete bracket
    # number (e.g. COMBO signals using Commander Spellbook's own per-combo bracket tag —
    # see bracket_signals.combo_signal). None means "no concrete floor known — the engine's
    # `_classify` should fall back to its own strength-based heuristic for this category."
    bracket_floor_hint: int | None = None

class Confidence(BaseModel):
    level: Literal["low", "medium", "high"]
    reasons: list[str]

class AssessmentWarning(BaseModel):
    code: str
    severity: Literal["warning", "error"]
    message: str

class BracketAssessment(BaseModel):
    schema_version: str = Field(default="1.0")
    engine_version: str
    rules_version: str
    data_version: str

    bracket: int
    bracket_name: str
    minimum_bracket: int
    maximum_bracket: int
    confidence: Confidence

    commanders: list[str] = Field(default_factory=list)
    official_signals: list[Signal] = Field(default_factory=list)
    heuristic_signals: list[Signal] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[AssessmentWarning] = Field(default_factory=list)
