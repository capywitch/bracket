import csv
from collections.abc import Iterator
from pathlib import Path

import pytest
from mtg_analyzer.data.db import CardDatabase
from mtg_analyzer.data.inventory_store import InventoryStore
from mtg_analyzer.ingest.decklist import (
    _COL,
    looks_like_archidekt_csv,
    parse_archidekt_csv,
    parse_deck,
    parse_decklist,
)
from mtg_analyzer.ingest.inventory import fix_mojibake, parse_inventory_csv
from mtg_analyzer.ingest.resolve import resolve_deck, resolve_inventory

FIXTURES = Path(__file__).parent / "fixtures"
SOL_RING = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
LLANOWAR = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture
def db(tmp_path: Path) -> Iterator[CardDatabase]:
    database = CardDatabase(tmp_path / "test.db")
    database.ingest_cards(FIXTURES / "oracle_cards_sample.json")
    yield database
    database.close()


# --- decklist parsing ------------------------------------------------------
def test_parse_archidekt_categories_and_commander() -> None:
    deck = parse_decklist((FIXTURES / "deck_archidekt.txt").read_text())
    assert deck.source_format == "archidekt"
    by_name = {e.name: e for e in deck.entries}
    atraxa = by_name["Atraxa, Praetors' Voice"]
    assert atraxa.section == "commander"  # from [Commander{top}] tag
    assert atraxa.set_code == "cmr"
    assert by_name["Sol Ring"].category == "Ramp"


def test_parse_card_name_with_parentheses_is_preserved() -> None:
    deck = parse_decklist((FIXTURES / "deck_archidekt.txt").read_text())
    names = {e.name for e in deck.entries}
    # The "(Not the Urza's Legacy One)" must NOT be mistaken for a (SET) suffix.
    assert "Erase (Not the Urza's Legacy One)" in names


def test_parse_arena_sections_and_foil() -> None:
    deck = parse_decklist((FIXTURES / "deck_arena.txt").read_text())
    sections = {e.name: e.section for e in deck.entries}
    assert sections["Llanowar Elves"] == "commander"
    assert sections["Sol Ring"] in {"main", "sideboard"}
    delver = next(e for e in deck.entries if e.name == "Delver of Secrets")
    assert delver.set_code == "ISD" and delver.collector_number == "51"  # *F* stripped
    assert any(e.section == "sideboard" for e in deck.entries)  # SB: line


def test_parse_manabox_comment_section_markers() -> None:
    # ManaBox marks the commander with "// COMMANDER" then a blank line before the deck.
    deck = parse_decklist((FIXTURES / "deck_manabox.txt").read_text())
    sections = {e.name: e.section for e in deck.entries}
    assert sections["Llanowar Elves"] == "commander"  # from "// COMMANDER"
    assert sections["Sol Ring"] == "main"  # blank line ended the commander block
    assert sections["Delver of Secrets"] == "main"


def test_parse_archidekt_csv_deck() -> None:
    text = (FIXTURES / "deck_archidekt.csv").read_text()
    assert looks_like_archidekt_csv(text)
    deck = parse_deck(text)  # auto-detects CSV vs text
    assert deck.source_format == "archidekt-csv"
    by_name = {e.name: e for e in deck.entries}
    assert by_name["Llanowar Elves"].section == "commander"  # category == Commander
    assert by_name["Sol Ring"].section == "main"
    assert by_name["Sol Ring"].set_code == "ltc" and by_name["Sol Ring"].collector_number == "284"
    assert by_name["Delver of Secrets"].section == "maybeboard"  # col-6 section hint


def test_parse_deck_routes_text_format() -> None:
    deck = parse_deck((FIXTURES / "deck_manabox.txt").read_text())
    assert deck.source_format != "archidekt-csv"  # routed to the text parser


def test_parse_decklist_no_marker_falls_back_to_first_card() -> None:
    # No section header, "// COMMANDER" comment, or [Commander] tag anywhere —
    # the first mainboard entry should be promoted to commander.
    text = "1 Atraxa, Praetors' Voice\n1 Sol Ring\n1 Command Tower\n"
    deck = parse_decklist(text)
    assert deck.explicit_commander is False
    sections = {e.name: e.section for e in deck.entries}
    assert sections["Atraxa, Praetors' Voice"] == "commander"
    assert sections["Sol Ring"] == "main"
    assert sections["Command Tower"] == "main"


def test_parse_decklist_no_marker_fallback_skips_sideboard_first_line() -> None:
    text = "SB: 1 Totally Fake Card\n1 Atraxa, Praetors' Voice\n1 Sol Ring\n"
    deck = parse_decklist(text)
    assert deck.explicit_commander is False
    sections = {e.name: e.section for e in deck.entries}
    assert sections["Totally Fake Card"] == "sideboard"
    assert sections["Atraxa, Praetors' Voice"] == "commander"  # first true mainboard entry
    assert sections["Sol Ring"] == "main"


def test_parse_decklist_explicit_marker_not_overridden() -> None:
    # Existing marker-based fixtures must keep flagging explicit_commander=True and
    # must not have the fallback touch anything else.
    deck = parse_decklist((FIXTURES / "deck_manabox.txt").read_text())
    assert deck.explicit_commander is True
    sections = {e.name: e.section for e in deck.entries}
    assert sections["Llanowar Elves"] == "commander"
    assert sections["Sol Ring"] == "main"


def test_parse_decklist_empty_has_no_commander() -> None:
    deck = parse_decklist("")
    assert deck.entries == []
    assert deck.explicit_commander is False


def test_parse_archidekt_csv_no_commander_row_falls_back_to_first() -> None:
    # Same fixture but with the Commander category stripped from Llanowar Elves' row.
    text = (FIXTURES / "deck_archidekt.csv").read_text()
    lines = text.splitlines()
    header_idx = next(i for i, line in enumerate(lines) if "Llanowar Elves" in line)
    row = next(csv.reader([lines[header_idx]]))
    row[_COL["category"]] = ""
    lines[header_idx] = ",".join(row)
    patched = "\n".join(lines) + "\n"

    deck = parse_archidekt_csv(patched)
    assert deck.explicit_commander is False
    by_name = {e.name: e for e in deck.entries}
    assert by_name["Llanowar Elves"].section == "commander"  # first mainboard row


def test_parse_archidekt_csv_explicit_commander_not_overridden() -> None:
    text = (FIXTURES / "deck_archidekt.csv").read_text()
    deck = parse_archidekt_csv(text)
    assert deck.explicit_commander is True
    by_name = {e.name: e for e in deck.entries}
    assert by_name["Llanowar Elves"].section == "commander"
    assert by_name["Sol Ring"].section == "main"


# --- deck resolution -------------------------------------------------------
def test_resolve_deck_attaches_cards_and_flags_unresolved(db: CardDatabase) -> None:
    deck = resolve_deck(db, parse_decklist((FIXTURES / "deck_arena.txt").read_text()))
    resolved = {e.requested_name: e for e in deck.entries if e.resolved}
    assert "Sol Ring" in resolved
    assert "Delver of Secrets" in resolved  # front-name resolves to the transform card
    assert [e.requested_name for e in deck.unresolved] == ["Totally Fake Card"]
    assert deck.commanders[0].card is not None
    assert deck.card_total(("commander", "main")) == 4  # excludes the SB: Sol Ring


# --- inventory parsing -----------------------------------------------------
def test_fix_mojibake() -> None:
    assert fix_mojibake("Troll of Khazad-dÃ»m") == "Troll of Khazad-dûm"
    assert fix_mojibake("Ãomer of the Riddermark").endswith("omer of the Riddermark")
    assert fix_mojibake("Sol Ring") == "Sol Ring"  # ASCII untouched
    assert fix_mojibake("Éowyn, Lady of Rohan") == "Éowyn, Lady of Rohan"  # correct text preserved


def test_parse_manabox_csv() -> None:
    items = parse_inventory_csv((FIXTURES / "inventory_manabox.csv").read_text())
    assert len(items) == 3
    foil_sol = next(i for i in items if i.name == "Sol Ring" and i.foil)
    assert foil_sol.quantity == 1 and foil_sol.set_code == "C21"
    assert foil_sol.purchase_price == 4.50
    assert items[0].scryfall_id == "11111111-1111-1111-1111-111111111111"


def test_resolve_card_splits_single_slash_dfc_name(db: CardDatabase) -> None:
    # User/export typed a single "/" (with spaces) instead of Scryfall's " // " join.
    from mtg_analyzer.ingest.resolve import resolve_card

    card = resolve_card(db, name="Delver of Secrets / Insectile Aberration")
    assert card is not None
    assert card.name == "Delver of Secrets // Insectile Aberration"


def test_resolve_card_flavor_name_fallback(db: CardDatabase) -> None:
    from mtg_analyzer.ingest.resolve import resolve_card

    card = resolve_card(db, name="Helm's Deep")
    assert card is not None
    assert card.name == "Shinka, the Bloodsoaked Keep"


def test_resolve_prefers_name_over_mismatched_set_collector(db: CardDatabase) -> None:
    # The (set, collector) here points at Llanowar Elves in the DB, but the name is
    # "Sol Ring" — name must win (set/collector from an export only have one
    # representative printing in the DB and can collide with a different card).
    from mtg_analyzer.ingest.resolve import resolve_card

    card = resolve_card(db, name="Sol Ring", set_code="m19", collector_number="314")
    assert card is not None and card.name == "Sol Ring"


def test_resolve_and_store_inventory(db: CardDatabase, tmp_path: Path) -> None:
    items = parse_inventory_csv((FIXTURES / "inventory_manabox.csv").read_text())
    inventory = resolve_inventory(db, items)
    assert inventory.distinct_cards == 2  # Sol Ring + Llanowar Elves
    assert inventory.owned(SOL_RING) == 3  # 2 nonfoil + 1 foil, aggregated by oracle_id

    store = InventoryStore(tmp_path / "test.db")
    try:
        assert store.replace(inventory) == 3
        assert store.owned(SOL_RING) == 3
        assert store.owned(LLANOWAR) == 3
        assert store.distinct_cards() == 2
        assert store.total_quantity() == 6
        printings = store.printings_for(SOL_RING)
        assert len(printings) == 2  # LTC + C21 retained separately
    finally:
        store.close()
