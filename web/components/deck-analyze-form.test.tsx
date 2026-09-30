import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { DeckAnalyzeForm } from "./deck-analyze-form";
import type { AnalyzeResponse } from "@/lib/types";
import { useActionState } from "react";

// Mock do React's useActionState and Next's form actions
// Como o DeckAnalyzeForm usa useActionState, precisamos mocká-lo para testes simples de renderização
vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  return {
    ...actual,
    useActionState: vi.fn(),
  };
});

// app/actions.ts puxa lib/api.ts (`import "server-only"`), que explode no jsdom —
// o componente só usa a referência da action como argumento de useActionState,
// então o stub basta pra isolar o teste de renderização do lado servidor.
vi.mock("@/app/actions", () => ({
  analyzeDeckAction: vi.fn(),
}));

test("renderiza sinais com source_type 'data' sem quebrar", () => {
  const mockResponse: AnalyzeResponse = {
    assessment: {
      schema_version: "1.0",
      engine_version: "1.0",
      rules_version: "1.0",
      data_version: "1.0",
      bracket: 4,
      bracket_name: "Optimized",
      minimum_bracket: 3,
      maximum_bracket: 4,
      confidence: { level: "high", reasons: [] },
      commanders: ["Sauron, the Dark Lord"],
      official_signals: [],
      heuristic_signals: [
        {
          id: "1",
          category: "EDHREC_SYNERGY",
          source_type: "data", // Esse valor quebrava o frontend
          strength: "high",
          evidence: [],
          explanation: "Alta sinergia no EDHREC",
        }
      ],
      evidence: [],
      warnings: [],
    },
    report_markdown: "",
    unresolved: [],
    warnings: [],
  };

  // Forçamos o estado inicial para exibir o resultado mockado
  vi.mocked(useActionState).mockReturnValue([{ result: mockResponse, error: null }, vi.fn(), false]);

  render(<DeckAnalyzeForm offline={false} />);

  // Verifica se o texto "Dados" ou a explicação renderiza corretamente
  expect(screen.getByText("Alta sinergia no EDHREC")).toBeDefined();
  expect(screen.getByText("Dados")).toBeDefined();
});
