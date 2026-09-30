from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from mtg_analyzer.analysis.bracket_adapter import to_assessment_deck
from mtg_analyzer.analysis.bracket_report import render_markdown
from mtg_analyzer.analysis.engine import AnalysisContext, BracketEngine, Ruleset
from mtg_analyzer.api.app import app
from mtg_analyzer.bracket_service import BracketService
from mtg_analyzer.combos.store import ComboStore
from mtg_analyzer.data.db import CardDatabase
from mtg_analyzer.models.card import Card
from mtg_analyzer.models.combo import Combo, ComboCard
from mtg_analyzer.models.deck import ResolvedDeck, ResolvedEntry

FIXTURES = Path(__file__).parent / "fixtures"
SOL_RING_OID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
LLANOWAR_OID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def make_card(name: str, **kw: Any) -> Card:
    base = {"id": name, "name": name, "layout": "normal", "cmc": 2.0,
            "type_line": "Creature", "oracle_text": "", "color_identity": [],
            "legalities": {"commander": "legal"}}
    base.update(kw)
    return Card.model_validate(base)


def entry(card: Card, *, section: str = "main", qty: int = 1) -> ResolvedEntry:
    return ResolvedEntry(quantity=qty, section=section, requested_name=card.name, card=card)


def unresolved_entry(name: str, *, section: str = "main") -> ResolvedEntry:
    return ResolvedEntry(quantity=1, section=section, requested_name=name, card=None)


def gc_ruleset() -> Ruleset:
    """A minimal in-memory ruleset naming Sol Ring a Game Changer (real ruleset data is
    versioned/external per CLAUDE.md — tests build their own small fixture instead of depending on
    which cards `rules/commander/2026-02.yaml` happens to list)."""
    return Ruleset({
        "version": "test-1",
        "brackets": {1: {"name": "Exhibition"}, 2: {"name": "Core"}, 3: {"name": "Upgraded"},
                     4: {"name": "Optimized"}, 5: {"name": "cEDH"}},
        "game_changers": [{"name": "Sol Ring", "oracle_id": SOL_RING_OID}],
    })


# --- bracket_adapter ---------------------------------------------------------
def test_to_assessment_deck_splits_sections_and_reports_unresolved() -> None:
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    main = make_card("Main Card", oracle_id="main-oid", cmc=3.0)
    comp = make_card("Companion Card", oracle_id="comp-oid")
    resolved = ResolvedDeck(name="Test Deck", entries=[
        entry(cmd, section="commander"),
        entry(main, section="main", qty=2),
        entry(comp, section="companion"),
        unresolved_entry("Totally Fake Card"),
    ])

    deck, unresolved = to_assessment_deck(resolved)

    assert unresolved == ["Totally Fake Card"]
    assert [dc.card.name for dc in deck.commander] == ["Cmdr"]
    assert deck.commander[0].is_commander
    assert [dc.card.name for dc in deck.cards] == ["Main Card"]
    assert deck.cards[0].quantity == 2
    assert deck.cards[0].card.mana_value == 3.0
    assert deck.companion is not None and deck.companion.card.name == "Companion Card"
    assert deck.companion.is_companion
    assert deck.source.type == "text"


# --- BracketEngine ------------------------------------------------------------
def _analysis_deck(entries: list[ResolvedEntry]) -> ResolvedDeck:
    return ResolvedDeck(name="Test", entries=entries)


def test_game_changer_pushes_bracket_to_optimized_range(tmp_path: Path) -> None:
    """1-3 Game Changers → Bracket 3 (Upgraded), per the official rules — only >3 GCs push to
    Bracket 4+. See `test_four_game_changers_pushes_to_optimized` for that threshold."""
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    sol_ring = make_card("Sol Ring", oracle_id=SOL_RING_OID)
    filler = [make_card(f"Filler {i}", oracle_id=f"filler-{i}") for i in range(98)]
    resolved = _analysis_deck(
        [entry(cmd, section="commander"), entry(sol_ring)]
        + [entry(c) for c in filler])
    deck, unresolved = to_assessment_deck(resolved)
    assert not unresolved

    combo_store = ComboStore(tmp_path / "combos.db")
    try:
        context = AnalysisContext(ruleset=gc_ruleset(), data_version="test", combo_store=combo_store)
        assessment = BracketEngine(context).analyze(deck)
    finally:
        combo_store.close()

    assert assessment.bracket == 3
    assert (assessment.minimum_bracket, assessment.maximum_bracket) == (3, 4)
    assert assessment.confidence.level == "high"
    assert len(assessment.official_signals) == 1
    assert assessment.official_signals[0].category == "GAME_CHANGER"
    assert assessment.evidence and "Sol Ring" in assessment.evidence[0].card_or_cards


def test_four_game_changers_pushes_to_optimized() -> None:
    """>3 Game Changers → floor 4 (Optimized), matching the official rule that 4+ Game Changers
    exceeds Bracket 3's allowance."""
    gc_names = [("Sol Ring", "gc-0"), ("Mana Vault", "gc-1"),
                ("Demonic Tutor", "gc-2"), ("Cyclonic Rift", "gc-3")]
    ruleset = Ruleset({
        "version": "test-1",
        "brackets": {1: {"name": "Exhibition"}, 2: {"name": "Core"}, 3: {"name": "Upgraded"},
                     4: {"name": "Optimized"}, 5: {"name": "cEDH"}},
        "game_changers": [{"name": n, "oracle_id": oid} for n, oid in gc_names],
    })
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    gc_cards = [make_card(n, oracle_id=oid) for n, oid in gc_names]
    filler = [make_card(f"Filler {i}", oracle_id=f"filler-{i}") for i in range(95)]
    resolved = _analysis_deck(
        [entry(cmd, section="commander")] + [entry(c) for c in gc_cards]
        + [entry(c) for c in filler])
    deck, unresolved = to_assessment_deck(resolved)
    assert not unresolved

    context = AnalysisContext(ruleset=ruleset, data_version="test")
    assessment = BracketEngine(context).analyze(deck)

    assert assessment.bracket == 4
    assert (assessment.minimum_bracket, assessment.maximum_bracket) == (4, 5)


def test_mass_land_denial_floors_bracket_4() -> None:
    """A symmetric, non-replacing land-destruction effect (Armageddon-style) floors Bracket 4 —
    spec §15."""
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    armageddon = make_card("Armageddon", oracle_id="arma-oid", oracle_text="Destroy all lands.")
    filler = [make_card(f"Filler {i}", oracle_id=f"filler-{i}") for i in range(98)]
    resolved = _analysis_deck(
        [entry(cmd, section="commander"), entry(armageddon)] + [entry(c) for c in filler])
    deck, unresolved = to_assessment_deck(resolved)
    assert not unresolved

    context = AnalysisContext(ruleset=gc_ruleset(), data_version="test")
    assessment = BracketEngine(context).analyze(deck)

    assert assessment.minimum_bracket >= 4
    assert any(s.category == "MASS_LAND_DENIAL" for s in assessment.official_signals)


def test_single_land_destruction_is_not_mass_land_denial() -> None:
    """Regression for spec §15: single-target land removal must NOT be flagged as mass land
    denial."""
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    strip = make_card("Land Destroyer", oracle_id="ld-oid", oracle_text="Destroy target land.")
    filler = [make_card(f"Filler {i}", oracle_id=f"filler-{i}") for i in range(98)]
    resolved = _analysis_deck(
        [entry(cmd, section="commander"), entry(strip)] + [entry(c) for c in filler])
    deck, unresolved = to_assessment_deck(resolved)
    assert not unresolved

    context = AnalysisContext(ruleset=gc_ruleset(), data_version="test")
    assessment = BracketEngine(context).analyze(deck)

    assert not any(s.category == "MASS_LAND_DENIAL" for s in assessment.official_signals)


def test_repeatable_extra_turn_floors_bracket_4() -> None:
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    engine_card = make_card(
        "Extra Turn Engine", oracle_id="et-oid", type_line="Artifact",
        oracle_text="Whenever you cast a spell, take an extra turn after this one.")
    filler = [make_card(f"Filler {i}", oracle_id=f"filler-{i}") for i in range(98)]
    resolved = _analysis_deck(
        [entry(cmd, section="commander"), entry(engine_card)] + [entry(c) for c in filler])
    deck, unresolved = to_assessment_deck(resolved)
    assert not unresolved

    context = AnalysisContext(ruleset=gc_ruleset(), data_version="test")
    assessment = BracketEngine(context).analyze(deck)

    assert assessment.minimum_bracket >= 4
    assert any(s.category == "EXTRA_TURN" for s in assessment.official_signals)


def test_single_extra_turn_floors_bracket_2() -> None:
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    time_warp = make_card("Time Warp", oracle_id="tw-oid", type_line="Sorcery",
                           oracle_text="Take an extra turn after this one.")
    filler = [make_card(f"Filler {i}", oracle_id=f"filler-{i}") for i in range(98)]
    resolved = _analysis_deck(
        [entry(cmd, section="commander"), entry(time_warp)] + [entry(c) for c in filler])
    deck, unresolved = to_assessment_deck(resolved)
    assert not unresolved

    context = AnalysisContext(ruleset=gc_ruleset(), data_version="test")
    assessment = BracketEngine(context).analyze(deck)

    assert assessment.minimum_bracket == 2
    assert assessment.maximum_bracket <= 3


def test_two_card_combo_via_combo_store(tmp_path: Path) -> None:
    """A 2-card combo WITHOUT a Commander Spellbook bracket_tag is suggestive, not determinative —
    floor 3, not 4. The old MV≤3 "early/cheap" heuristic floored every low-MV 2-card combo at 4,
    which caught casual synergies (Jolly Balloon Man + Village Bell-Ringer, Breath of Fury +
    Éowyn) that aren't cEDH win-cons. Authoritative tags (ruthless/powerful) still floor 4."""
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    piece_a = make_card("Combo Piece A", oracle_id="combo-a")
    piece_b = make_card("Combo Piece B", oracle_id="combo-b")
    filler = [make_card(f"Filler {i}", oracle_id=f"filler-{i}") for i in range(97)]
    resolved = _analysis_deck(
        [entry(cmd, section="commander"), entry(piece_a), entry(piece_b)]
        + [entry(c) for c in filler])
    deck, unresolved = to_assessment_deck(resolved)
    assert not unresolved

    combo = Combo(
        id="combo-1", produces=["Infinite mana"], identity="C",
        uses=[ComboCard(oracle_id="combo-a", name="Combo Piece A"),
              ComboCard(oracle_id="combo-b", name="Combo Piece B")],
        requires=[],
    )
    combo_store = ComboStore(tmp_path / "combos.db")
    combo_store.add([combo])
    try:
        context = AnalysisContext(ruleset=gc_ruleset(), data_version="test", combo_store=combo_store)
        assessment = BracketEngine(context).analyze(deck)
    finally:
        combo_store.close()

    assert assessment.minimum_bracket == 3
    assert any(s.category == "TWO_CARD_COMBO" for s in assessment.official_signals)


def test_missing_combo_store_notes_incomplete_data() -> None:
    """`combo_store is None` means "unknown", not "no combos" — confidence drops to medium with an
    explanatory reason, rather than silently reporting high confidence on incomplete data."""
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    filler = [make_card(f"Filler {i}", oracle_id=f"filler-{i}") for i in range(99)]
    resolved = _analysis_deck([entry(cmd, section="commander")] + [entry(c) for c in filler])
    deck, unresolved = to_assessment_deck(resolved)
    assert not unresolved

    context = AnalysisContext(ruleset=gc_ruleset(), data_version="test")  # combo_store=None
    assessment = BracketEngine(context).analyze(deck)

    assert assessment.confidence.level == "medium"
    assert any("combo data" in r.lower() for r in assessment.confidence.reasons)


def test_fast_mana_and_tutor_are_heuristic_only() -> None:
    """Fast mana and tutors are heuristic/informational — they must not by themselves push the
    bracket range above the unconstrained baseline (spec §18/§19)."""
    ruleset = Ruleset({
        "version": "test-1",
        "brackets": {1: {"name": "Exhibition"}, 2: {"name": "Core"}, 3: {"name": "Upgraded"},
                     4: {"name": "Optimized"}, 5: {"name": "cEDH"}},
        "game_changers": [],
        "fast_mana": [{"name": "Sol Ring"}, {"name": "Mana Vault"}, {"name": "Mana Crypt"}],
    })
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    sol_ring = make_card("Sol Ring", oracle_id="sol-oid")
    mana_vault = make_card("Mana Vault", oracle_id="vault-oid")
    mana_crypt = make_card("Mana Crypt", oracle_id="crypt-oid")
    tutor = make_card("Demonic Tutor", oracle_id="tutor-oid",
                       oracle_text="Search your library for a card, put it into your hand.")
    filler = [make_card(f"Filler {i}", oracle_id=f"filler-{i}") for i in range(95)]
    resolved = _analysis_deck(
        [entry(cmd, section="commander"), entry(sol_ring), entry(mana_vault),
         entry(mana_crypt), entry(tutor)] + [entry(c) for c in filler])
    deck, unresolved = to_assessment_deck(resolved)
    assert not unresolved

    context = AnalysisContext(ruleset=ruleset, data_version="test")
    assessment = BracketEngine(context).analyze(deck)

    assert not any(s.source_type == "official" for s in assessment.heuristic_signals)
    assert any(s.category == "FAST_MANA" for s in assessment.heuristic_signals)
    assert any(s.category == "TUTOR" for s in assessment.heuristic_signals)
    assert assessment.minimum_bracket == 1
    assert assessment.maximum_bracket <= 3


def test_missing_commander_is_low_confidence_error() -> None:
    resolved = _analysis_deck([entry(make_card("Just A Card", oracle_id="x"))])
    deck, _ = to_assessment_deck(resolved)

    context = AnalysisContext(ruleset=gc_ruleset(), data_version="test")
    assessment = BracketEngine(context).analyze(deck)

    assert any(w.code == "MISSING_COMMANDER" and w.severity == "error"
               for w in assessment.warnings)
    assert assessment.confidence.level == "low"


def test_wrong_deck_size_is_medium_confidence_warning() -> None:
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    resolved = _analysis_deck([entry(cmd, section="commander"), entry(make_card("Only One", oracle_id="x"))])
    deck, _ = to_assessment_deck(resolved)

    context = AnalysisContext(ruleset=gc_ruleset(), data_version="test")
    assessment = BracketEngine(context).analyze(deck)

    assert any(w.code == "INVALID_DECK_SIZE" and w.severity == "warning"
               for w in assessment.warnings)
    assert assessment.confidence.level == "medium"


# --- render_markdown -----------------------------------------------------------
def test_render_markdown_smoke() -> None:
    cmd = make_card("Cmdr", oracle_id="cmd-oid", type_line="Legendary Creature — Elf")
    resolved = _analysis_deck([entry(cmd, section="commander")])
    deck, unresolved = to_assessment_deck(resolved)

    context = AnalysisContext(ruleset=gc_ruleset(), data_version="test")
    assessment = BracketEngine(context).analyze(deck)
    md = render_markdown(assessment, deck, unresolved)

    assert f"## Bracket {assessment.bracket}" in md
    assert "## Methodology" in md
    assert "Rule Zero" in md
    assert "## Official Signals" in md


# --- BracketService / API ------------------------------------------------------
def test_bracket_service_analyze_decklist_end_to_end(tmp_path: Path) -> None:
    db = CardDatabase(tmp_path / "test.db")
    db.ingest_cards(FIXTURES / "oracle_cards_sample.json")
    try:
        service = BracketService(db=db, ruleset=gc_ruleset(),
                                  combo_db_path=tmp_path / "combos.db")
        report = service.analyze_decklist(
            (FIXTURES / "deck_manabox.txt").read_text(), name="Sample")
        assert report.assessment.schema_version == "1.0"
        # 1 Game Changer (Sol Ring) in a small/invalid-size deck → floor 3, ceiling 4.
        assert report.assessment.bracket == 3
        assert report.unresolved == []
        assert "## Bracket" in report.markdown
    finally:
        db.close()


def test_analyze_endpoint(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    seed_db = CardDatabase(db_path)
    seed_db.ingest_cards(FIXTURES / "oracle_cards_sample.json")
    seed_db.close()

    with TestClient(app) as client:
        # `db_path` (not a live `db`) so the connection opens lazily inside the request thread —
        # see BracketService's docstring on why a pre-built db can't cross threads safely here.
        client.app.state.bracket_service.close()
        client.app.state.bracket_service = BracketService(
            db_path=db_path, ruleset=gc_ruleset(), combo_db_path=tmp_path / "combos.db")

        resp = client.post("/api/v1/analyze", json={
            "decklist": (FIXTURES / "deck_manabox.txt").read_text(),
            "name": "Sample",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["assessment"]["schema_version"] == "1.0"
        assert "report_markdown" in body and "## Bracket" in body["report_markdown"]


def test_analyze_endpoint_rejects_empty_decklist() -> None:
    with TestClient(app) as client:
        resp = client.post("/api/v1/analyze", json={"decklist": "   "})
        assert resp.status_code == 422
