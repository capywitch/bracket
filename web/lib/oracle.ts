import "server-only";

import {
  buildPriceRows,
  type MarketLatestMin,
  type OraclePrinting,
  type PriceRow,
} from "@/lib/prices";

/**
 * Cliente server-only da API do Oracle (tcgrp.oracle) para preços de referência.
 * Sem `ORACLE_API_URL` configurado, ou com o Oracle fora do ar, devolve lista vazia:
 * preço é complemento e nunca derruba a análise do deck.
 */

const ORACLE_API_URL = process.env.ORACLE_API_URL;
const REVALIDATE_SECONDS = 3600;

async function oracleGet<T>(path: string): Promise<T> {
  const res = await fetch(`${ORACLE_API_URL}${path}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: REVALIDATE_SECONDS },
  });
  if (!res.ok) throw new Error(`Oracle respondeu ${res.status} para ${path}`);
  return (await res.json()) as T;
}

/** Preços de referência (Liga, MYP Cards, TCGplayer, Cardmarket) da impressão principal da carta. */
export async function getCardPriceRows(name: string): Promise<PriceRow[]> {
  if (!ORACLE_API_URL) return [];
  try {
    const card = await oracleGet<{ default_printing: (OraclePrinting & { id: string }) | null }>(
      `/v1/games/magic/cards/by-name?name=${encodeURIComponent(name)}`,
    );
    const printing = card.default_printing;
    if (!printing) return [];
    const latest = await oracleGet<Record<string, MarketLatestMin[]>>(
      `/v1/market/printings/latest-min?ids=${printing.id}`,
    ).catch(() => ({}) as Record<string, MarketLatestMin[]>);
    return buildPriceRows(latest[printing.id], printing);
  } catch {
    return [];
  }
}
