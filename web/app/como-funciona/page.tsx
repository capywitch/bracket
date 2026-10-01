import { Fragment } from "react";

import { BracketBadge } from "@/components/bracket-badge";
import { CardImage, CardNameLink } from "@/components/card-image";
import { ColorPips } from "@/components/color-pips";
import { Panel } from "@/components/panel";
import {
  getGameChangerNames,
  getGameChangersWithColors,
  getRulesVersion,
  getSignalKeys,
} from "@/lib/rules/game-changers";

const WUBRG = ["W", "U", "B", "R", "G"] as const;

const COLOR_GROUP_LABELS: Record<string, string> = {
  W: "Branco",
  U: "Azul",
  B: "Preto",
  R: "Vermelho",
  G: "Verde",
  multi: "Multicolor",
  C: "Incolor",
};

function groupByColor(
  cards: { name: string; colors: string[] }[],
): { key: string; cards: { name: string; identity: string }[] }[] {
  const groups = new Map<string, { name: string; identity: string }[]>();

  for (const { name, colors } of cards) {
    const key =
      colors.length === 0 ? "C" : colors.length === 1 ? colors[0] : "multi";
    const identity = colors.length === 0 ? "C" : colors.join("");
    groups.set(key, [...(groups.get(key) ?? []), { name, identity }]);
  }

  const order = [...WUBRG, "multi", "C"];
  return order
    .filter((key) => groups.has(key))
    .map((key) => ({
      key,
      cards: groups.get(key)!.sort((a, b) => a.name.localeCompare(b.name)),
    }));
}

const TIERS: { tier: number; description: string }[] = [
  {
    tier: 1,
    description:
      "Exhibition: decks temáticos e ultra-casuais, montados pra diversão em torno de um tema, não pra vencer com eficiência.",
  },
  {
    tier: 2,
    description:
      "Core: nível de deck pronto de loja (precon), sem otimizações agressivas. Ponto de partida da maioria das mesas.",
  },
  {
    tier: 3,
    description:
      "Upgraded: deck ajustado com melhorias pontuais, permite até 3 Game Changers, curva mais consistente.",
  },
  {
    tier: 4,
    description:
      "Optimized: alto poder, sem restrição de Game Changers, mas ainda abaixo do padrão totalmente competitivo.",
  },
  {
    tier: 5,
    description:
      "cEDH: competitivo de ponta a ponta, com combos rápidos, interação máxima e mana eficiente ao extremo.",
  },
];

const SOURCES: { label: string; href: string; note: string }[] = [
  {
    label: "Introducing Commander Brackets (Beta)",
    href: "https://magic.wizards.com/en/news/announcements/introducing-commander-brackets-beta",
    note: "Anúncio oficial da Wizards of the Coast do sistema de 5 brackets e da lista de Game Changers.",
  },
  {
    label: "Commander Brackets Beta Update",
    href: "https://magic.wizards.com/en/news/announcements/commander-brackets-beta-update-february-9-2026",
    note: "Atualizações periódicas da Wizards sobre a lista de Game Changers e as regras de bracket.",
  },
  {
    label: "Regras oficiais do formato Commander",
    href: "https://mtgcommander.net/index.php/rules/",
    note: "100 cartas, singleton, identidade de cor, vida inicial e demais regras do formato.",
  },
  {
    label: "Scryfall",
    href: "https://scryfall.com",
    note: "Dados e imagens de carta, usados via Fan Content Policy da Wizards.",
  },
  {
    label: "Commander Spellbook",
    href: "https://commanderspellbook.com",
    note: "Base de combos usada pra detectar peças de combo prontas no deck.",
  },
  {
    label: "Commander Spellbook: Syntax guide (bracket tags)",
    href: "https://commanderspellbook.com/syntax-guide/#bracket",
    note: "Classificação de bracket que o próprio Commander Spellbook atribui a cada combo, usada pra estimar a força de um combo encontrado no deck.",
  },
  {
    label: "The Command Zone: Commander Deckbuilding Template",
    href: "https://www.youtube.com/watch?v=OSNV6224cHg",
    note: "Base de métricas heurísticas para curvas e limites percentuais (ex: meta de 15% de interação).",
  },
];

function CardNameList({ names }: { names: string[] }) {
  return (
    <>
      {names.map((name, i) => (
        <Fragment key={name}>
          {i > 0 ? ", " : null}
          <CardNameLink name={name} />
        </Fragment>
      ))}
    </>
  );
}

export default function ComoFuncionaPage() {
  const gameChangers = getGameChangerNames();
  const gameChangersByColor = groupByColor(getGameChangersWithColors());
  const rulesVersion = getRulesVersion();

  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <h1 className="text-3xl font-semibold text-fg">
        Como calculamos o Bracket
      </h1>
      <p className="mt-3 text-justify text-muted">
        O sistema de brackets é oficial da Wizards of the Coast, pensado pra
        ajudar grupos a combinarem mesas com nível de poder parecido antes de
        sentar pra jogar. O Meus Brackets estima em qual das 5 faixas o seu deck
        se encaixa a partir de alguns sinais: presença de{" "}
        <strong className="text-fg">Game Changers</strong>, presença de{" "}
        <strong className="text-fg">combos</strong> prontos e sinais
        adicionais. A estimativa <strong className="text-fg">não</strong> é uma
        nota somada/ponderada. É um sistema de{" "}
        <strong className="text-fg">piso e teto</strong>: cada sinal oficial
        empurra o piso pra cima de forma independente.
      </p>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-fg">Regras do formato</h2>
        <p className="mt-3 text-justify text-muted">
          Commander é jogado com exatamente{" "}
          <strong className="text-fg">100 cartas</strong> (99 + 1 comandante),
          em modo <strong className="text-fg">singleton</strong>: nenhum nome
          repetido, exceto terrenos básicos. O comandante precisa ser uma
          criatura lendária (ou uma carta que diga explicitamente &ldquo;pode ser seu
          comandante&rdquo;), e toda carta do deck precisa ter identidade de cor{" "}
          <strong className="text-fg">dentro</strong> da identidade do
          comandante. Cada jogador começa com{" "}
          <strong className="text-fg">40 pontos de vida</strong>.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-fg">Os 5 tiers</h2>
        <div className="mt-4 space-y-3">
          {TIERS.map(({ tier, description }) => (
            <div
              key={tier}
              className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,220px)_1fr]"
            >
              <BracketBadge tier={tier} size="lg" className="flex-1" />
              <Panel>
                <p className="text-justify text-sm text-muted">{description}</p>
              </Panel>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-2xl font-semibold text-fg">Critérios e Sinais</h2>
        <p className="mt-3 text-justify text-muted">
          Abaixo estão listados os componentes individuais que analisamos no seu deck
          e como cada um afeta o cálculo do bracket. Partes de um mesmo tema foram agrupadas.
        </p>

        <div className="mt-6 space-y-8">
          {/* GAME CHANGERS */}
          <div>
            <h3 className="text-lg font-semibold text-fg">1. Game Changers</h3>
            <p className="mt-2 text-justify text-sm text-muted">
              É uma lista curada e periodicamente revisada pela própria Wizards. Cartas
              dessa lista distorcem o jogo de forma desproporcional. 
              <br/><strong className="text-fg mt-1 block">Regra do Piso:</strong> 
              0 Game Changers resulta em piso 1; de 1 a 3, piso pelo menos 3; 
              4 ou mais, piso pelo menos 4. Lista completa (regras versão {rulesVersion}, {gameChangers.length} cartas):
            </p>
            <div className="mt-4 space-y-6">
              {gameChangersByColor.map(({ key, cards }) => (
                <div key={key}>
                  <div className="flex items-center gap-2">
                    {key === "multi" || key === "C" ? (
                      <span className="text-sm font-medium text-fg">{COLOR_GROUP_LABELS[key]}</span>
                    ) : (
                      <ColorPips identity={key} />
                    )}
                    {key !== "multi" && key !== "C" && (
                      <span className="text-sm font-medium text-fg">{COLOR_GROUP_LABELS[key]}</span>
                    )}
                    <span className="text-sm text-muted">({cards.length})</span>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-5">
                    {cards.map(({ name, identity }) => (
                      <figure key={name}>
                        <CardImage name={name} />
                        <figcaption className="mt-1.5 text-xs text-muted">
                          {name}
                          {key === "multi" && (
                            <span className="mt-1 block"><ColorPips identity={identity} /></span>
                          )}
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* COMBOS */}
          <div>
            <h3 className="text-lg font-semibold text-fg">2. Combos</h3>
            <p className="mt-2 text-justify text-sm text-muted">
              O Meus Brackets olha se o deck tem peças que juntas geram um loop infinito 
              ou uma vitória imediata, baseando-se no Commander Spellbook.
              <br/><strong className="text-fg mt-1 block">Regra do Piso:</strong> 
              Usa a bracket tag que o Commander Spellbook atribui ao combo quando ela existe: 
              piso 4 para Ruthless, piso 3 para Powerful/Spicy, piso 2 para Oddball/Core, 
              piso 1 para Exhibition. Sem essa classificação (combo sem tag reconhecida), 
              o piso mínimo vai pro bracket 3, independente do custo de mana das peças envolvidas.
            </p>
          </div>

          {/* TURNOS EXTRAS */}
          <div>
            <h3 className="text-lg font-semibold text-fg">3. Turnos Extras</h3>
            <p className="mt-2 text-justify text-sm text-muted">
              Efeitos que dão turnos adicionais (ex.: <CardNameList names={["Time Warp", "Nexus of Fate"]} />). 
              Multiplicam o número de land drops, ativações e ataques do jogador.
              <br/><strong className="text-fg mt-1 block">Regra do Piso:</strong> 
              Se o efeito é repetível/encadeável (um permanente, ou um feitiço com texto do tipo 
              &ldquo;sempre que&rdquo;/&ldquo;no início de&rdquo;), o piso da estimativa vai pra pelo menos o bracket 4; 
              se é um feitiço avulso, de uso único, o piso é pelo menos o bracket 2.
            </p>
          </div>

          {/* NEGAÇÃO DE TERRENOS */}
          <div>
            <h3 className="text-lg font-semibold text-fg">4. Negação de Terrenos em Massa</h3>
            <p className="mt-2 text-justify text-sm text-muted">
              Cartas que destroem ou travam os terrenos de todos os oponentes 
              (ex.: <CardNameList names={["Armageddon", "Winter Orb"]} />).
              <br/><strong className="text-fg mt-1 block">Regra do Piso:</strong> 
              É considerado um efeito de alto impacto pelo próprio sistema de brackets da Wizards: 
              uma única ocorrência já trava o piso da estimativa em pelo menos o bracket 4.
            </p>
          </div>

          {/* AJUSTE FINO & TETO */}
          <div>
            <h3 className="text-lg font-semibold text-fg">5. Ajuste Fino, Teto e Mana Rápida</h3>
            <p className="mt-2 text-justify text-sm text-muted">
              Após calcular os pisos de todos os critérios acima, verificamos os sinais heurísticos 
              (como a aceleração de mana muito acima da curva normal, ex.: <CardNameList names={["Sol Ring", "Mana Crypt", "Ancient Tomb"]} />).
              <br/><strong className="text-fg mt-1 block">Regras de Teto e Ajuste:</strong> 
              O teto é sempre pelo menos o bracket 3, ou piso + 1 quando o piso já passou de 2 (limitado ao bracket 5).
              A estimativa final sobe 1 bracket acima do piso (sem nunca ultrapassar o teto) se o número de
              gatilhos fortes abaixo atingir um limiar: <strong className="text-fg">2 gatilhos</strong> quando
              o piso calculado é 3 ou menos, ou <strong className="text-fg">3 gatilhos</strong> quando o piso
              já é 4 ou mais (cada gatilho conta no máximo 1 vez, mesmo que o deck exceda o limite listado):
            </p>
            <ul className="mt-3 list-disc pl-5 space-y-2 text-sm text-muted">
              <li>
                <strong className="text-fg font-medium">Interação Alta (≥ 15% das não-terrenos):</strong> Baseada nos templates clássicos da comunidade (como <em>The Command Zone</em>), que recomendam 10 peças de interação (remoção, proteção, anulações) para rodar de forma eficiente. Em um deck padrão de 65 cartas não-terreno, 10 peças equivalem a cerca de 15%.
              </li>
              <li>
                <strong className="text-fg font-medium">Mana Rápida Curada (≥ 3 peças):</strong> Presença de 3 ou mais aceleradores explosivos de uma lista curada (como Sol Ring, Mana Crypt, Mox Diamond, etc), indicando vantagem explosiva de curva nos primeiros turnos.
              </li>
              <li>
                <strong className="text-fg font-medium">Tutor Amplo (≥ 1 peça):</strong> Presença de qualquer tutor irrestrito (que não limita a busca a um subtipo específico como Terreno ou Criatura), indicando consistência para buscar a resposta exata ou peça de combo na hora certa.
              </li>
            </ul>
            <p className="mt-3 text-justify text-sm text-muted">
              <strong className="text-fg mt-1 block">Métrica Informacional: Velocidade do deck</strong>
              Calculamos um indicador de velocidade (Baixa / Média / Alta) somando pontos: <strong>(1)</strong> média de custo (MV) não-terreno ≤ 2.5; <strong>(2)</strong> ≥ 2 peças de mana rápida; <strong>(3)</strong> densidade de tutores ≥ 5%; <strong>(4)</strong> presença de pelo menos 1 combo. Velocidade alta (3-4 pts) ou média (1-2 pts) aparecem no relatório final apenas como contexto de metagame, mas <strong>não</strong> alteram o cálculo de bracket sozinhos.
            </p>
          </div>

        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-fg">Fontes</h2>
        <p className="mt-3 text-justify text-muted">
          As informações desta página vêm das seguintes fontes oficiais e de
          terceiros:
        </p>
        <ul className="mt-4 space-y-3">
          {SOURCES.map(({ label, href, note }) => (
            <li key={href} className="text-sm">
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                className="text-accent-secondary hover:underline"
              >
                {label}
              </a>
              <span className="block text-muted">{note}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
