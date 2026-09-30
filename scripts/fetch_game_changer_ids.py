"""
Fetch oracle_ids for all Game Changers from Scryfall batch API.
Run: python scripts/fetch_game_changer_ids.py
Output: prints YAML entries ready to paste into rules/commander/2026-02.yaml
"""

import time

import httpx

GAME_CHANGERS = [
    "Ad Nauseam", "Ancient Tomb", "Aura Shards", "Biorhythm",
    "Bolas's Citadel", "Braids, Cabal Minion", "Chrome Mox",
    "Coalition Victory", "Consecrated Sphinx", "Crop Rotation",
    "Cyclonic Rift", "Demonic Tutor", "Drannith Magistrate",
    "Enlightened Tutor", "Farewell", "Field of the Dead",
    "Fierce Guardianship", "Force of Will", "Gaea's Cradle",
    "Gamble", "Gifts Ungiven", "Glacial Chasm",
    "Grand Arbiter Augustin IV", "Grim Monolith", "Humility",
    "Imperial Seal", "Intuition", "Jeska's Will",
    "Lion's Eye Diamond", "Mana Vault", "Mishra's Workshop",
    "Mox Diamond", "Mystical Tutor", "Narset, Parter of Veils",
    "Natural Order", "Necropotence", "Notion Thief",
    "Opposition Agent", "Orcish Bowmasters", "Panoptic Mirror",
    "Rhystic Study", "Seedborn Muse", "Serra's Sanctum",
    "Smothering Tithe", "Survival of the Fittest", "Teferi's Protection",
    "Tergrid, God of Fright", "Thassa's Oracle", "The One Ring",
    "The Tabernacle at Pendrell Vale", "Underworld Breach",
    "Vampiric Tutor", "Worldly Tutor",
]

HEADERS = {
    "User-Agent": "MeusBrackets/0.1 (fale@tcgrp.com.br)",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def main():
    results = []
    not_found = []

    for batch in chunks(GAME_CHANGERS, 75):
        identifiers = [{"name": name} for name in batch]
        resp = httpx.post(
            "https://api.scryfall.com/cards/collection",
            headers=HEADERS,
            json={"identifiers": identifiers},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("data", []))
        not_found.extend(data.get("not_found", []))
        time.sleep(0.1)  # Rate limit: ~100ms gap

    print("# Game Changers with oracle_ids")
    print("game_changers:")
    for card in sorted(results, key=lambda c: c["name"]):
        colors = ", ".join(f'"{c}"' for c in card.get("color_identity", []))
        print(f'  - name: "{card["name"]}"')
        print(f'    oracle_id: "{card["oracle_id"]}"')
        print(f'    colors: [{colors}]')

    if not_found:
        print("\n# NOT FOUND:")
        for nf in not_found:
            print(f"  # {nf}")

if __name__ == "__main__":
    main()
