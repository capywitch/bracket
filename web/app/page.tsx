import Link from "next/link";

import { CardImage } from "@/components/card-image";
import { DeckAnalyzeForm } from "@/components/deck-analyze-form";
import { HeroBrand } from "@/components/hero-brand";
import { getHealth } from "@/lib/api";
import {
  getGameChangerNames,
  getRulesVersion,
} from "@/lib/rules/game-changers";

export default async function HomePage() {
  let backendOffline = false;
  try {
    await getHealth();
  } catch {
    backendOffline = true;
  }

  const gameChangers = getGameChangerNames();
  const rulesVersion = getRulesVersion();
  const featuredCards = [...gameChangers]
    .sort(() => Math.random() - 0.5)
    .slice(0, 4);

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-14 px-6 py-16">
      <HeroBrand />

      <DeckAnalyzeForm offline={backendOffline} />

      <div>
        <h2 className="text-2xl font-semibold text-fg">
          Qual é o nível de poder do seu deck de Commander?
        </h2>
        <p className="mt-4 text-muted">
          O Meus Brackets analisa sua lista e estima em qual dos 5 brackets oficiais ela se
          encaixa, do mais casual ao competitivo, apontando o que empurra o deck
          pra cima ou pra baixo na escala. Assim fica mais fácil combinar mesas
          com um nível de poder parecido.
        </p>
        <Link
          href="/decks"
          className="mt-6 inline-block text-sm text-accent-primary hover:underline"
        >
          Ver exemplos de análise
        </Link>
      </div>

      <section>
        <h2 className="text-xl font-semibold text-fg">
          Como calculamos o Bracket
        </h2>
        <p className="mt-3 text-muted">
          A escala vai de <strong className="text-fg">1 (Exhibition)</strong> a{" "}
          <strong className="text-fg">5 (cEDH)</strong>. O principal fator são
          as <strong className="text-fg">Game Changers</strong>, um grupo de
          cartas que a própria Wizards define como especialmente fortes pro
          formato: nenhuma nos brackets 1 e 2, até 3 no bracket 3, sem limite
          dali pra cima. Também entram na conta combos prontos, turnos extras,
          negação de terrenos em massa e mana muito acelerada.
        </p>

        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {featuredCards.map((name) => (
            <figure key={name}>
              <CardImage name={name} />
              <figcaption className="mt-1.5 text-xs text-muted">
                {name}
              </figcaption>
            </figure>
          ))}
        </div>

        <p className="mt-4 text-xs text-muted">
          Regras versão {rulesVersion} · {gameChangers.length} Game Changers no
          total. Clique numa carta pra ver a arte em tela cheia.
        </p>

        <Link
          href="/como-funciona"
          className="mt-4 inline-block text-sm text-accent-secondary hover:underline"
        >
          Ver metodologia completa
        </Link>
      </section>
    </main>
  );
}
