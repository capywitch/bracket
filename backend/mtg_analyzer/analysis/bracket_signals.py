"""Per-category signal detectors for the Bracket Engine (docs/spec/bracket-engine.md §11-22).

Each function inspects a `Deck` (the lightweight `models.assessment` shapes — plain
`.oracle_text`/`.mana_value` attributes, not the rich Scryfall `models.card.Card`) and returns a
single `Signal | None`: `None` means the category found nothing to report. Detection reuses
`categorize.py`'s oracle-text regex idiom rather than inventing a new one.

The engine (`engine.py`) decides which of these run (via `Ruleset.signal_enabled`) and how their
results affect classification — these functions only detect and explain, never classify (spec
§3.5, "no magic scoring": each category stays a distinct, explainable signal).
"""

from __future__ import annotations

import re
from typing import Literal

from mtg_analyzer.combos.store import ComboStore
from mtg_analyzer.models.assessment import Deck, DeckCard, Evidence, EvidenceSource, Signal

# --- shared helpers ----------------------------------------------------------

_RE_EXTRA_TURN = re.compile(r"takes? an extra turn|additional turn after this one", re.S)
_RE_RECURRING_WORDING = re.compile(r"\bwhenever\b|\bat the beginning of\b", re.S)

_RE_MLD_EACH_PLAYER = re.compile(r"each player (sacrifices|discards|exiles).{0,30}lands?", re.S)
_RE_MLD_ALL_LANDS = re.compile(r"destroy all lands|exile all lands|all lands? .{0,20}destroyed", re.S)
_RE_MLD_DONT_UNTAP = re.compile(r"lands? (don'?t|do not) untap", re.S)
_RE_MLD_NONBASIC = re.compile(r"nonbasic lands? (are|is|become)", re.S)

_RE_TUTOR = re.compile(r"search your library for (a|an|up to|two|three|that)", re.S)
_RE_TUTOR_NARROW_TYPE = re.compile(
    r"search your library for (a|an|up to \w+|two|three) [^.\n]{0,20}?"
    r"(artifact|enchantment|creature|instant|sorcery|planeswalker)\b", re.S
)

#: Commander Spellbook's own per-combo classification (`bracketTag` on `Combo`, parsed in
#: `models/combo.py`) mapped to the bracket number it implies — see
#: https://commanderspellbook.com/syntax-guide/#bracket. `None` (banned/unrecognized) means
#: "don't use this to set a floor" — `banned` combos use a card illegal in Commander, which
#: shouldn't appear in a legal decklist anyway. Keys are lowercase; lookups normalize the raw
#: tag before matching, since the API's casing isn't pinned by a local fixture.
_BRACKET_TAG_FLOOR: dict[str, int | None] = {
    "ruthless": 4,
    "powerful": 3,
    "spicy": 3,
    "oddball": 2,
    "core": 2,
    "exhibition": 1,
    "banned": None,
}

_RE_REMOVAL = re.compile(
    r"(destroy|exile) target|deals? \d+ damage to (target|any target)|"
    r"target (creature|permanent) gets [-−]", re.S
)
_RE_WIPE = re.compile(
    r"destroy all|exile all|destroy each|all creatures get [-−]|"
    r"each player sacrifices|destroy the rest", re.S
)
_RE_COUNTER = re.compile(r"counter target", re.S)
_RE_GRAVEYARD_HATE = re.compile(r"exile.{0,20}graveyard", re.S)
_RE_PROTECTION = re.compile(r"hexproof|indestructible|protection from|can'?t be countered", re.S)


def _all_cards(deck: Deck) -> list[DeckCard]:
    return deck.cards + deck.commander + ([deck.companion] if deck.companion else [])


def _nonland_cards(deck: Deck) -> list[DeckCard]:
    return [dc for dc in _all_cards(deck) if "land" not in dc.card.type_line.lower()]


def _text(dc: DeckCard) -> str:
    return dc.card.oracle_text.lower()


def _ev_id(prefix: str, dc: DeckCard) -> str:
    return f"ev-{prefix}-{dc.card.oracle_id or dc.card.name}"


# --- official signals ---------------------------------------------------------

def game_changer_signal(deck: Deck, ruleset) -> Signal | None:  # type: ignore[no-untyped-def]
    evidence = []
    for dc in _all_cards(deck):
        is_gc = (dc.card.oracle_id in ruleset.game_changers_by_id
                 or dc.card.name in ruleset.game_changers_by_name)
        if is_gc:
            evidence.append(Evidence(
                id=_ev_id("gc", dc),
                type="game_changer",
                source=EvidenceSource(type="official", rules_version=ruleset.version),
                card_or_cards=[dc.card.name],
                description=f"{dc.card.name} is listed as a Game Changer.",
                impact="high",
            ))
    if not evidence:
        return None
    return Signal(
        id="sig-official-gc",
        category="GAME_CHANGER",
        source_type="official",
        strength="high",
        evidence=evidence,
        explanation=f"Found {len(evidence)} Game Changer(s).",
    )


def combo_signal(deck: Deck, ruleset, combo_store: ComboStore | None) -> Signal | None:  # type: ignore[no-untyped-def]
    """TWO_CARD_COMBO / MULTI_CARD_COMBO via the offline `ComboStore` (spec §39/§68: the engine
    never touches the network — combo lookups are cache-only). `combo_store is None` (no cache
    populated yet) means "unknown", not "no combos" — callers should note reduced confidence, not
    treat this as a clean negative."""
    if combo_store is None:
        return None

    cards = _all_cards(deck)
    oracle_ids = {dc.card.oracle_id for dc in cards if dc.card.oracle_id}
    if not oracle_ids:
        return None
    mana_value_by_id = {dc.card.oracle_id: dc.card.mana_value for dc in cards if dc.card.oracle_id}

    found = combo_store.find_in_deck(oracle_ids)
    if not found.included:
        return None

    evidence = []
    any_two_card = False
    any_early_cheap = False
    max_tag_floor: int | None = None  # highest bracket floor implied by a recognized bracket_tag
    for combo in found.included:
        names = [u.name for u in combo.uses]
        is_two_card = len(combo.uses) == 2
        is_early_cheap = is_two_card and all(
            (mana_value_by_id.get(u.oracle_id) or 0) <= 3 for u in combo.uses if u.oracle_id
        )
        if is_two_card:
            any_two_card = True
        if is_early_cheap:
            any_early_cheap = True

        tag = (combo.bracket_tag or "").strip().lower()
        tag_floor = _BRACKET_TAG_FLOOR.get(tag)
        if tag_floor is not None:
            max_tag_floor = tag_floor if max_tag_floor is None else max(max_tag_floor, tag_floor)
            extra_note = f" (Commander Spellbook bracket tag: {tag})"
        elif is_early_cheap:
            # No usable tag (unrecognized/missing/banned) — fall back to the MV≤3 heuristic.
            extra_note = " (both pieces cheap/early, mana value ≤ 3 — heuristic threshold)"
        else:
            extra_note = ""

        category = "TWO_CARD_COMBO" if is_two_card else "MULTI_CARD_COMBO"
        impact: Literal["low", "medium", "high"] = "high" if (tag_floor is not None and tag_floor >= 4) or \
                             (tag_floor is None and is_early_cheap) else \
                  "low" if (tag_floor is not None and tag_floor <= 2) else "medium"
        evidence.append(Evidence(
            id=f"ev-combo-{combo.id}",
            type=category.lower(),
            source=EvidenceSource(type="data", rules_version=ruleset.version),
            card_or_cards=names,
            description=f"{' + '.join(names)} form a combo ({', '.join(combo.produces) or 'unspecified result'}){extra_note}.",
            impact=impact,
        ))

    explanation = f"Found {len(found.included)} complete combo(s) in the decklist (offline combo cache)."
    if max_tag_floor is None:
        strength: Literal["low", "medium", "high"] = "high" if any_early_cheap else "medium"
    else:
        strength = "high" if max_tag_floor >= 4 else "medium" if max_tag_floor == 3 else "low"
    return Signal(
        id="sig-official-combo",
        category="TWO_CARD_COMBO" if any_two_card else "COMBO",
        source_type="data",
        strength=strength,
        evidence=evidence,
        explanation=explanation + (" At least one is early/cheap." if any_early_cheap else ""),
        bracket_floor_hint=max_tag_floor,
    )


def extra_turn_signal(deck: Deck, ruleset) -> Signal | None:  # type: ignore[no-untyped-def]
    evidence = []
    any_repeatable = False
    for dc in _all_cards(deck):
        text = _text(dc)
        if not _RE_EXTRA_TURN.search(text):
            continue
        type_line = dc.card.type_line.lower()
        is_permanent = not any(k in type_line for k in ("instant", "sorcery"))
        is_repeatable = is_permanent or bool(_RE_RECURRING_WORDING.search(text))
        if is_repeatable:
            any_repeatable = True
        evidence.append(Evidence(
            id=_ev_id("extra-turn", dc),
            type="extra_turn",
            source=EvidenceSource(type="official", rules_version=ruleset.version),
            card_or_cards=[dc.card.name],
            description=f"{dc.card.name} grants an extra turn"
                        + (" (repeatable/chainable)." if is_repeatable else " (one-shot spell)."),
            impact="high" if is_repeatable else "medium",
        ))
    if not evidence:
        return None
    return Signal(
        id="sig-official-extra-turn",
        category="EXTRA_TURN",
        source_type="official",
        strength="high" if any_repeatable else "medium",
        evidence=evidence,
        explanation=f"Found {len(evidence)} extra-turn effect(s)"
                    + (", including repeatable/chainable ones." if any_repeatable else "."),
    )


def mass_land_denial_signal(deck: Deck, ruleset) -> Signal | None:  # type: ignore[no-untyped-def]
    evidence = []
    for dc in _all_cards(deck):
        text = _text(dc)
        if not (_RE_MLD_EACH_PLAYER.search(text) or _RE_MLD_ALL_LANDS.search(text)
                or _RE_MLD_DONT_UNTAP.search(text) or _RE_MLD_NONBASIC.search(text)):
            continue
        evidence.append(Evidence(
            id=_ev_id("mld", dc),
            type="mass_land_denial",
            source=EvidenceSource(type="official", rules_version=ruleset.version),
            card_or_cards=[dc.card.name],
            description=f"{dc.card.name} symmetrically denies/destroys multiple players' lands.",
            impact="high",
        ))
    if not evidence:
        return None
    return Signal(
        id="sig-official-mld",
        category="MASS_LAND_DENIAL",
        source_type="official",
        strength="high",
        evidence=evidence,
        explanation=f"Found {len(evidence)} mass land denial effect(s) "
                    "(symmetric, non-replacing — single-target land removal doesn't count).",
    )


# --- heuristic signals ---------------------------------------------------------

def fast_mana_signal(deck: Deck, ruleset) -> Signal | None:  # type: ignore[no-untyped-def]
    fast_mana_by_id = ruleset.fast_mana_by_id
    fast_mana_by_name = ruleset.fast_mana_by_name
    evidence = []
    nonland = _nonland_cards(deck)
    for dc in _all_cards(deck):
        if dc.card.oracle_id in fast_mana_by_id or dc.card.name in fast_mana_by_name:
            evidence.append(Evidence(
                id=_ev_id("fast-mana", dc),
                type="fast_mana",
                source=EvidenceSource(type="heuristic", rules_version=ruleset.version),
                card_or_cards=[dc.card.name],
                description=f"{dc.card.name} is a curated fast-mana staple.",
                impact="medium",
            ))
    if not evidence:
        return None
    density = len(evidence) / len(nonland) if nonland else 0.0
    return Signal(
        id="sig-heuristic-fast-mana",
        category="FAST_MANA",
        source_type="heuristic",
        strength="high" if len(evidence) >= 3 else "medium",
        evidence=evidence,
        explanation=f"{len(evidence)} fast-mana card(s), {density:.0%} of nonland cards "
                    "(heuristic only — does not by itself set the bracket).",
    )


def tutor_signal(deck: Deck, ruleset) -> Signal | None:  # type: ignore[no-untyped-def]
    evidence = []
    broad_count = 0
    narrow_count = 0
    nonland = _nonland_cards(deck)
    for dc in _all_cards(deck):
        text = _text(dc)
        if not _RE_TUTOR.search(text):
            continue
        if "land" in dc.card.type_line.lower():
            continue  # land ramp tutors are RAMP, not TUTOR (matches categorize.py's split)
        is_narrow = bool(_RE_TUTOR_NARROW_TYPE.search(text))
        if is_narrow:
            narrow_count += 1
        else:
            broad_count += 1
        evidence.append(Evidence(
            id=_ev_id("tutor", dc),
            type="tutor",
            source=EvidenceSource(type="heuristic", rules_version=ruleset.version),
            card_or_cards=[dc.card.name],
            description=f"{dc.card.name} tutors for a card ({'narrow' if is_narrow else 'broad'}).",
            impact="low",
        ))
    if not evidence:
        return None
    density = len(evidence) / len(nonland) if nonland else 0.0
    return Signal(
        id="sig-heuristic-tutor",
        category="TUTOR",
        source_type="heuristic",
        strength="medium" if broad_count else "low",
        evidence=evidence,
        explanation=f"{len(evidence)} tutor(s) ({broad_count} broad, {narrow_count} narrow), "
                    f"{density:.0%} density. Tutors are consistency/heuristic signal only — "
                    "no longer bracket-restricting per the Oct 2025 rules update.",
    )


def interaction_signal(deck: Deck, ruleset) -> Signal | None:  # type: ignore[no-untyped-def]
    buckets = {"removal": 0, "board_wipe": 0, "counterspell": 0, "graveyard_hate": 0, "protection": 0}
    evidence = []
    nonland = _nonland_cards(deck)
    for dc in _all_cards(deck):
        text = _text(dc)
        hit = None
        if _RE_WIPE.search(text):
            hit = "board_wipe"
        elif _RE_REMOVAL.search(text):
            hit = "removal"
        elif _RE_COUNTER.search(text):
            hit = "counterspell"
        elif _RE_GRAVEYARD_HATE.search(text):
            hit = "graveyard_hate"
        elif _RE_PROTECTION.search(text):
            hit = "protection"
        if hit is None:
            continue
        buckets[hit] += 1
        evidence.append(Evidence(
            id=_ev_id("interaction", dc),
            type=hit,
            source=EvidenceSource(type="heuristic", rules_version=ruleset.version),
            card_or_cards=[dc.card.name],
            description=f"{dc.card.name} provides {hit.replace('_', ' ')}.",
            impact="low",
        ))
    if not evidence:
        return None
    density = len(evidence) / len(nonland) if nonland else 0.0
    summary = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in buckets.items() if v)
    return Signal(
        id="sig-heuristic-interaction",
        category="INTERACTION",
        source_type="heuristic",
        strength="high" if density >= 0.15 else "medium" if density >= 0.08 else "low",
        evidence=evidence,
        explanation=f"{len(evidence)} interaction piece(s) ({summary}), {density:.0%} density. "
                    "High interaction density is expected at brackets 4-5; very low interaction "
                    "typically points to lower brackets.",
    )


def deck_speed_signal(deck: Deck, ruleset, fast_mana_count: int, tutor_density: float,
                       has_combo: bool) -> Signal | None:  # type: ignore[no-untyped-def]
    """Heuristic low/medium/high estimate from avg nonland mana value, fast mana, tutor density,
    and combo presence — curve thresholds per the commander-format skill (peak MV 2–3 is
    typical/expected)."""
    nonland = _nonland_cards(deck)
    if not nonland:
        return None
    avg_mv = sum(dc.card.mana_value for dc in nonland) / len(nonland)

    score = 0
    if avg_mv <= 2.5:
        score += 1
    if fast_mana_count >= 2:
        score += 1
    if tutor_density >= 0.05:
        score += 1
    if has_combo:
        score += 1

    speed = "high" if score >= 3 else "medium" if score >= 1 else "low"
    return Signal(
        id="sig-heuristic-deck-speed",
        category="DECK_SPEED",
        source_type="heuristic",
        strength="medium",
        evidence=[Evidence(
            id="ev-deck-speed",
            type="deck_speed",
            source=EvidenceSource(type="heuristic", rules_version=ruleset.version),
            card_or_cards=[],
            description=f"Average nonland mana value {avg_mv:.2f}, {fast_mana_count} fast-mana "
                        f"card(s), tutor density {tutor_density:.0%}, "
                        f"combo {'present' if has_combo else 'absent'} → {speed} deck speed.",
            impact="low",
        )],
        explanation=f"Estimated deck speed: {speed} "
                    "(context signal only — does not by itself set the bracket).",
    )
