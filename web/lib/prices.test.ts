import { describe, expect, it } from "vitest";

import { buildPriceRows, type MarketLatestMin } from "@/lib/prices";

const norm = (t: string) => t.replace(/\u00a0/g, " ");

const market: MarketLatestMin[] = [
  { source: "tcgplayer", label: "TCGplayer", minCents: 426, currency: "USD", day: "2026-11-15", url: "https://tcgplayer.com/p/1" },
  { source: "myp", label: "MYP Cards", minCents: 2500, currency: "BRL", day: "2026-11-15", url: "https://myp.com/x" },
  { source: "liga", label: "Liga", minCents: 2890, currency: "BRL", day: "2026-11-15", url: "https://liga.com/x", finishes: { normal: 3295, foil: 2890 } },
];

describe("buildPriceRows", () => {
  it("ordem: MYP/Liga (R$), TCGplayer (US$), Cardmarket (€), com datas e links", () => {
    const rows = buildPriceRows(market, {
      attributes: { prices: { usd: "3.16", eur: "2.61" } },
      tcgplayer_updated_at: "2026-11-15T03:00:00Z",
      cardmarket_url: "https://www.cardmarket.com/x",
    });
    const text = rows.map((r) => norm(`${r.label}: ${r.value} ${r.day}`));
    expect(text).toEqual([
      "MYP Cards: R$ 25,00 15/11/2026",
      "Liga: Normal R$ 32,95 · Foil R$ 28,90 15/11/2026",
      "TCGplayer: US$ 4,26 15/11/2026",
      "Cardmarket: € 2,61 15/11/2026",
    ]);
    expect(rows.map((r) => r.url)).toEqual([
      "https://myp.com/x",
      "https://liga.com/x",
      "https://tcgplayer.com/p/1",
      "https://www.cardmarket.com/x",
    ]);
  });

  it("Cardmarket sem link vira texto; sem preço nenhum, lista vazia", () => {
    const rows = buildPriceRows(undefined, { attributes: { prices: { eur: "2.61" } } });
    expect(rows).toHaveLength(1);
    expect(rows[0].url).toBeUndefined();
    expect(buildPriceRows(undefined, null)).toEqual([]);
  });
});
