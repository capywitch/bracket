"use client";

import { useState } from "react";
import { CardZoomDialog, ZoomableCardImage } from "@capywitch/ui/components/ZoomableCardImage";

// Proxy local (`app/api/card-image`) que busca no Scryfall e cacheia em disco —
// evita hotlink direto do browser, que sob a rajada de imagens de uma grade de
// deck perdia várias por rate limit. Versão "normal" sempre, nunca
// art_crop/border_crop, que cortam a linha de copyright/artista (proibido pelo
// CLAUDE.md da raiz).
function scryfallImageUrl(name: string): string {
  return `/api/card-image?name=${encodeURIComponent(name)}`;
}

export function CardImage({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  return (
    <ZoomableCardImage
      src={scryfallImageUrl(name)}
      alt={name}
      loading="lazy"
      imgClassName={`aspect-5/7 w-full rounded-xl overflow-hidden object-cover ${className ?? ""}`}
    />
  );
}

/**
 * Menção de carta dentro de texto corrido (regras, explicações de sinais
 * etc.) — mesma ideia de clique-pra-ver da grade de Game Changers, só que
 * como um link inline em vez de uma figura em bloco.
 */
export function CardNameLink({ name, className }: { name: string; className?: string }) {
  const [open, setOpen] = useState(false);
  const src = scryfallImageUrl(name);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`cursor-zoom-in truncate text-left text-accent-secondary underline decoration-dotted underline-offset-2 hover:decoration-solid ${className ?? ""}`}
        aria-label={`Ver ${name} em tela cheia`}
      >
        {name}
      </button>

      {open ? <CardZoomDialog src={src} alt={name} onClose={() => setOpen(false)} /> : null}
    </>
  );
}
