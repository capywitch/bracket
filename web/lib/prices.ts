/**
 * Preços de referência de uma carta, vindos da API do Oracle (tcgrp.oracle).
 * Formato igual ao "Preços referência" do Oracle web: Liga e MYP Cards (R$),
 * TCGplayer (US$) e Cardmarket (€), cada um com data e link para o mercado.
 * Módulo puro (sem `server-only`): o formatador roda no servidor, o tipo é usado no client.
 */

export interface PriceRow {
  id: string;
  label: string;
  value: string;
  /** `dd/mm/aaaa` ou null quando a fonte não informa a data. */
  day: string | null;
  url?: string;
}

export interface MarketLatestMin {
  source: string;
  label: string;
  minCents: number;
  currency?: "BRL" | "USD";
  day: string | null;
  url?: string | null;
  finishes?: { normal: number; foil: number };
}

export interface OraclePrinting {
  attributes?: { prices?: unknown } | null;
  tcgplayer_price?: number | null;
  tcgplayer_url?: string | null;
  tcgplayer_updated_at?: string | null;
  cardmarket_url?: string | null;
}

type Currency = "BRL" | "USD" | "EUR";

const money = (value: number, currency: Currency) =>
  value.toLocaleString("pt-BR", { style: "currency", currency });

/** `YYYY-MM-DD[...]` -> `dd/mm/aaaa` sem passar por Date (evita deslocar o dia por fuso). */
export function fmtDay(day: string): string {
  const [y, m, d] = day.slice(0, 10).split("-");
  return y && m && d ? `${d}/${m}/${y}` : day;
}

const STORE_GROUPS: { label: string; currency: "USD" | "EUR"; keys: [string, string][] }[] = [
  { label: "TCGplayer", currency: "USD", keys: [["usd", "Normal"], ["usd_foil", "Foil"], ["usd_etched", "Etched"]] },
  { label: "Cardmarket", currency: "EUR", keys: [["eur", "Normal"], ["eur_foil", "Foil"]] },
];

function joinFinishes(parts: [string, string][]): string {
  const plain = parts.length === 1 && parts[0][0] === "Normal";
  return parts.map(([finish, v]) => (plain ? v : `${finish} ${v}`)).join(" · ");
}

const isUsdTcgplayer = (p: MarketLatestMin) => p.source === "tcgplayer" && p.currency === "USD";

function marketValue(p: MarketLatestMin): string {
  const cur = p.currency ?? "BRL";
  return p.finishes
    ? `Normal ${money(p.finishes.normal / 100, cur)} · Foil ${money(p.finishes.foil / 100, cur)}`
    : money(p.minCents / 100, cur);
}

/** Linhas na ordem: reais (Liga, MYP Cards), TCGplayer (US$), Cardmarket (€). */
export function buildPriceRows(
  marketPrices: MarketLatestMin[] | undefined,
  printing: OraclePrinting | null | undefined,
): PriceRow[] {
  const usdMarket = marketPrices?.find(isUsdTcgplayer);
  const reais: PriceRow[] = (marketPrices ?? [])
    .filter((p) => !isUsdTcgplayer(p))
    .map((p) => ({
      id: `${p.source}-${p.currency ?? "BRL"}`,
      label: p.label,
      value: marketValue(p),
      day: p.day ? fmtDay(p.day) : null,
      url: p.url ?? undefined,
    }));

  const raw = printing?.attributes?.prices;
  const prices = (typeof raw === "object" && raw !== null ? raw : {}) as Record<string, string | null>;
  const has = (key: string) => prices[key] !== null && prices[key] !== undefined;
  const catalogDay = printing?.tcgplayer_updated_at ?? null;

  const stores = STORE_GROUPS.flatMap((g): PriceRow[] => {
    const parts: [string, string][] = [];
    for (const [key, finish] of g.keys) {
      let n: number | null = has(key) ? Number(prices[key]) : null;
      if (g.currency === "USD" && key === "usd") {
        if (usdMarket) {
          n = (usdMarket.finishes ? usdMarket.finishes.normal : usdMarket.minCents) / 100;
        } else if (n === null && typeof printing?.tcgplayer_price === "number") {
          n = printing.tcgplayer_price;
        }
      }
      if (n !== null && Number.isFinite(n)) parts.push([finish, money(n, g.currency)]);
    }
    if (g.currency === "USD" && usdMarket?.finishes && !has("usd_foil")) {
      parts.push(["Foil", money(usdMarket.finishes.foil / 100, "USD")]);
    }
    if (parts.length === 0) return [];
    const isTcg = g.currency === "USD";
    const day = isTcg && usdMarket ? usdMarket.day : catalogDay;
    return [
      {
        id: g.currency,
        label: g.label,
        value: joinFinishes(parts),
        day: day ? fmtDay(day) : null,
        url: isTcg
          ? (usdMarket?.url ?? printing?.tcgplayer_url ?? undefined)
          : (printing?.cardmarket_url ?? undefined),
      },
    ];
  });
  return [...reais, ...stores];
}
