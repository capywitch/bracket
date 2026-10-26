import { DecksBrowser } from "@/components/decks-browser";
import { listDecks } from "@/lib/mock/deck-service";

export default async function DecksPage() {
  const decks = await listDecks();

  return (
    <main className="mx-auto max-w-7xl px-6 py-16">
      <h1 className="text-3xl font-semibold text-fg">Decks</h1>
      <p className="mt-2 text-muted">Análise de bracket dos seus decks de Commander.</p>

      <DecksBrowser decks={decks} />
    </main>
  );
}
