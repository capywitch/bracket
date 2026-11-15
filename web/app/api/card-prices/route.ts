import type { NextRequest } from "next/server";

import { getCardPriceRows } from "@/lib/oracle";

/** Preços de referência de uma carta (via Oracle), buscados só quando o modal abre. */
export async function GET(request: NextRequest) {
  const name = request.nextUrl.searchParams.get("name");
  if (!name || !name.trim()) {
    return new Response("Missing `name` query param.", { status: 400 });
  }
  const rows = await getCardPriceRows(name.trim());
  return Response.json(
    { rows },
    { headers: { "Cache-Control": "public, max-age=900, stale-while-revalidate=3600" } },
  );
}
