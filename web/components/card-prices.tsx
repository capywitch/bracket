"use client";

import { useEffect, useState } from "react";

import type { PriceRow } from "@/lib/prices";

type State = { status: "loading" } | { status: "done"; rows: PriceRow[] };

/**
 * Rodapé do modal da carta: "Preços referência" com Liga, MYP Cards, TCGplayer e
 * Cardmarket (valor, data e link para o mercado). Só monta com o modal aberto,
 * então a busca no Oracle acontece sob demanda. Sem preço, não mostra nada.
 */
export function CardPrices({ name }: { name: string }) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/card-prices?name=${encodeURIComponent(name)}`, { signal: controller.signal })
      .then((res) => (res.ok ? (res.json() as Promise<{ rows: PriceRow[] }>) : { rows: [] }))
      .then(({ rows }) => setState({ status: "done", rows }))
      .catch((err) => {
        if (!controller.signal.aborted) setState({ status: "done", rows: [] });
        void err;
      });
    return () => controller.abort();
  }, [name]);

  if (state.status === "loading") {
    return <span className="text-xs text-white/60">Carregando preços…</span>;
  }
  if (state.rows.length === 0) return null;

  return (
    <>
      <span className="text-white/60">Preços referência</span>
      <ul className="flex flex-col items-center gap-0.5">
        {state.rows.map((row) => (
          <li key={row.id}>
            {row.url ? (
              <a
                href={row.url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-white/60 underline hover:text-white"
              >
                {row.label}:
              </a>
            ) : (
              <span className="text-white/60">{row.label}:</span>
            )}{" "}
            <span className="font-medium">{row.value}</span>
            {row.day && <span className="ml-1 text-xs text-white/60">{row.day}</span>}
          </li>
        ))}
      </ul>
    </>
  );
}
