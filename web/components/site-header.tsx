import { SiteHeader as CapywitchSiteHeader } from "@capywitch/ui/components/SiteHeader";

/** Header global — CapyWitch + nome "Meus Brackets" + subtítulo de afiliação TCGRP, nav simples. */
export function SiteHeader() {
  return (
    <CapywitchSiteHeader
      logoSrc="/capywitch.png"
      logoWidth={408}
      logoHeight={612}
      brand="Meus Brackets"
      subtitle="Analista de Bracket da TCGRP"
      navItems={[
        { href: "/decks", label: "Decks" },
        { href: "/como-funciona", label: "Como funciona" },
      ]}
    />
  );
}
