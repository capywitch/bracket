from pathlib import Path

import yaml  # type: ignore[import-untyped]  # pyyaml stubs not declared in pyproject (upstream-owned)

from mtg_analyzer.analysis import bracket_signals
from mtg_analyzer.combos.store import ComboStore
from mtg_analyzer.models.assessment import (
    AssessmentWarning,
    BracketAssessment,
    Confidence,
    Deck,
    Signal,
)

DEFAULT_RULES_DIR = Path(__file__).resolve().parent.parent / "rules" / "commander"

class Ruleset:
    def __init__(self, data: dict):
        self.version = data.get("version", "unknown")
        self.brackets = data.get("brackets", {})

        self.game_changers_by_id = {}
        self.game_changers_by_name = set()

        for gc in data.get("game_changers", []):
            if gc.get("oracle_id"):
                self.game_changers_by_id[gc["oracle_id"]] = gc.get("name", "")
            if gc.get("name"):
                self.game_changers_by_name.add(gc["name"])

        self.fast_mana_by_id = {}
        self.fast_mana_by_name = set()

        for fm in data.get("fast_mana", []):
            if fm.get("oracle_id"):
                self.fast_mana_by_id[fm["oracle_id"]] = fm.get("name", "")
            if fm.get("name"):
                self.fast_mana_by_name.add(fm["name"])

        self.signals = data.get("signals", {})

    def signal_enabled(self, key: str) -> bool:
        """Whether a signal category is turned on — defaults to `True` when absent so older
        ruleset files (no `signals:` block for a given key) keep working unchanged."""
        return self.signals.get(key, {}).get("enabled", True)

    @classmethod
    def load(cls, filepath: str | Path) -> "Ruleset":
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(data)


def load_latest_ruleset(rules_dir: Path | None = None) -> Ruleset:
    """Load the most recent versioned ruleset (filenames are `YYYY-MM.yaml`, so lexicographic
    order is chronological order). Rules are data, never hard-coded — see docs/spec/bracket-engine.md
    §10 and CLAUDE.md's "treat the Game Changers list as external, versioned data" rule."""
    directory = rules_dir or DEFAULT_RULES_DIR
    files = sorted(directory.glob("*.yaml"))
    if not files:
        raise FileNotFoundError(f"No ruleset files found in {directory}")
    return Ruleset.load(files[-1])

class AnalysisContext:
    def __init__(self, ruleset: Ruleset, data_version: str, engine_version: str = "0.1.0",
                 combo_store: ComboStore | None = None):
        self.ruleset = ruleset
        self.data_version = data_version
        self.engine_version = engine_version
        # Optional: offline-only combo cache (see bracket_signals.combo_signal). The engine never
        # opens one itself and never touches the network during ordinary classification — spec
        # §39/§68. `None` means "no combo data available", handled as reduced confidence rather
        # than "no combos found".
        self.combo_store = combo_store

class BracketEngine:
    def __init__(self, context: AnalysisContext):
        self.context = context

    def analyze(self, deck: Deck) -> BracketAssessment:
        warnings = self._validate(deck)

        official_signals = self._extract_official_signals(deck)
        heuristic_signals = self._extract_heuristic_signals(deck, official_signals)

        all_evidence = []
        for sig in official_signals + heuristic_signals:
            all_evidence.extend(sig.evidence)

        bracket, min_b, max_b = self._classify(official_signals, heuristic_signals)
        bracket_name = self.context.ruleset.brackets.get(bracket, {}).get("name", f"Bracket {bracket}")

        confidence = self._estimate_confidence(deck, warnings)

        return BracketAssessment(
            engine_version=self.context.engine_version,
            rules_version=self.context.ruleset.version,
            data_version=self.context.data_version,
            bracket=bracket,
            bracket_name=bracket_name,
            minimum_bracket=min_b,
            maximum_bracket=max_b,
            confidence=confidence,
            official_signals=official_signals,
            heuristic_signals=heuristic_signals,
            evidence=all_evidence,
            warnings=warnings
        )

    def _validate(self, deck: Deck) -> list[AssessmentWarning]:
        warnings = []
        # Basic validation
        if not deck.commander:
            warnings.append(AssessmentWarning(
                code="MISSING_COMMANDER",
                severity="error",
                message="Deck has no commander specified."
            ))

        card_count = sum(c.quantity for c in deck.cards) + sum(c.quantity for c in deck.commander)
        if deck.companion:
            card_count += deck.companion.quantity

        if card_count != 100:
            warnings.append(AssessmentWarning(
                code="INVALID_DECK_SIZE",
                severity="warning",
                message=f"Deck contains {card_count} cards instead of 100."
            ))

        return warnings

    def _extract_official_signals(self, deck: Deck) -> list[Signal]:
        ruleset = self.context.ruleset
        signals: list[Signal] = []

        if ruleset.signal_enabled("game_changers"):
            sig = bracket_signals.game_changer_signal(deck, ruleset)
            if sig:
                signals.append(sig)

        if ruleset.signal_enabled("combos"):
            sig = bracket_signals.combo_signal(deck, ruleset, self.context.combo_store)
            if sig:
                signals.append(sig)

        if ruleset.signal_enabled("extra_turns"):
            sig = bracket_signals.extra_turn_signal(deck, ruleset)
            if sig:
                signals.append(sig)

        if ruleset.signal_enabled("mass_land_denial"):
            sig = bracket_signals.mass_land_denial_signal(deck, ruleset)
            if sig:
                signals.append(sig)

        return signals

    def _extract_heuristic_signals(self, deck: Deck, official_signals: list[Signal]) -> list[Signal]:
        ruleset = self.context.ruleset
        signals: list[Signal] = []

        fast_mana_sig = None
        if ruleset.signal_enabled("fast_mana"):
            fast_mana_sig = bracket_signals.fast_mana_signal(deck, ruleset)
            if fast_mana_sig:
                signals.append(fast_mana_sig)

        tutor_sig = None
        if ruleset.signal_enabled("tutors"):
            tutor_sig = bracket_signals.tutor_signal(deck, ruleset)
            if tutor_sig:
                signals.append(tutor_sig)

        if ruleset.signal_enabled("interaction"):
            sig = bracket_signals.interaction_signal(deck, ruleset)
            if sig:
                signals.append(sig)

        if ruleset.signal_enabled("deck_speed"):
            fast_mana_count = len(fast_mana_sig.evidence) if fast_mana_sig else 0
            nonland = [dc for dc in deck.cards + deck.commander
                       if "land" not in dc.card.type_line.lower()]
            tutor_density = (len(tutor_sig.evidence) / len(nonland)) if tutor_sig and nonland else 0.0
            has_combo = any(s.category in ("TWO_CARD_COMBO", "COMBO", "MULTI_CARD_COMBO")
                             for s in official_signals)
            sig = bracket_signals.deck_speed_signal(deck, ruleset, fast_mana_count, tutor_density,
                                                     has_combo)
            if sig:
                signals.append(sig)

        return signals

    def _classify(self, official: list[Signal], heuristic: list[Signal]) -> tuple[int, int, int]:
        """Constraint-based floor/ceiling per the official Commander Brackets rules — ordered
        checks, never a weighted/summed score (spec §3.5 "no magic scoring"). Each official signal
        independently raises the floor; heuristic signals only nudge the point estimate within the
        [floor, ceiling] range they never expand on their own (spec §18/§19)."""
        floor = 1
        ceiling = 3

        by_category = {s.category: s for s in official}

        gc_sig = by_category.get("GAME_CHANGER")
        gc_count = len(gc_sig.evidence) if gc_sig else 0
        if gc_count > 3:
            floor = max(floor, 4)
        elif gc_count >= 1:
            floor = max(floor, 3)

        if "MASS_LAND_DENIAL" in by_category:
            floor = max(floor, 4)

        extra_turn_sig = by_category.get("EXTRA_TURN")
        if extra_turn_sig:
            repeatable = extra_turn_sig.strength == "high"
            floor = max(floor, 4 if repeatable else 2)

        combo_sig = by_category.get("TWO_CARD_COMBO") or by_category.get("COMBO") \
            or by_category.get("MULTI_CARD_COMBO")
        if combo_sig:
            if combo_sig.bracket_floor_hint is not None:
                # Commander Spellbook's own per-combo bracket tag is available — trust it over
                # the MV≤3 heuristic (it can floor as low as 2 for an "oddball"/"core" combo,
                # not just 3/4 like the old heuristic-only path).
                floor = max(floor, combo_sig.bracket_floor_hint)
            else:
                # No authoritative tag — treat combo as suggestive, not determinative. The old
                # MV≤3 "early/cheap" heuristic floored every 2-card low-MV combo at 4, which
                # catches far too many casual/value combos (Jolly Balloon Man + Village
                # Bell-Ringer, Breath of Fury + Éowyn) that are synergies, not cEDH win-cons.
                floor = max(floor, 3)

        ceiling = max(ceiling, min(floor + 1, 5))
        floor = min(floor, 5)

        # Heuristic signals nudge the point estimate to the top of the legal range without ever
        # expanding it themselves — they contribute, they don't determine (spec §18/§19). Nudge is
        # deliberately conservative: a single medium-strength heuristic signal (e.g. one tutor, a
        # couple of fast-mana rocks) isn't enough on its own. At low floors (≤3) it takes **two**
        # strong indicators; at high floors (≥4) it takes **three** — pushing a Bracket-4 deck to
        # cEDH on heuristics alone requires overwhelming evidence, since Bracket 5 is a competitive
        # format with distinct meta expectations (spec §3.5: no magic scoring).
        heuristic_by_category = {s.category: s for s in heuristic}
        strong_signals = 0
        fast_mana_sig = heuristic_by_category.get("FAST_MANA")
        if fast_mana_sig and fast_mana_sig.strength == "high":
            strong_signals += 1
        tutor_sig = heuristic_by_category.get("TUTOR")
        if tutor_sig and tutor_sig.strength == "medium":
            strong_signals += 1
        interaction_sig = heuristic_by_category.get("INTERACTION")
        if interaction_sig and interaction_sig.strength == "high":
            strong_signals += 1

        nudge_threshold = 3 if floor >= 4 else 2
        nudge = strong_signals >= nudge_threshold
        bracket = min(ceiling, floor + 1) if nudge else floor
        bracket = max(floor, min(bracket, ceiling))

        return bracket, floor, ceiling

    def _estimate_confidence(self, deck: Deck, warnings: list[AssessmentWarning]) -> Confidence:
        if any(w.severity == "error" for w in warnings):
            return Confidence(level="low", reasons=["Critical errors in validation."])

        reasons = []
        if any(w.severity == "warning" for w in warnings):
            reasons.append("Warnings present during validation.")

        if self.context.combo_store is None:
            reasons.append(
                "No combo data available — TWO_CARD_COMBO signal skipped (INCOMPLETE_COMBO_DATA).")

        if reasons:
            return Confidence(level="medium", reasons=reasons)

        return Confidence(level="high", reasons=["Deck is fully valid and resolved."])
