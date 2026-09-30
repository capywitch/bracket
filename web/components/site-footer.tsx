import {
  SiteFooter as CapywitchSiteFooter,
  FooterLink,
} from "@capywitch/ui/components/SiteFooter";

/** Rodapé global: sobre o site, afiliação TCGRP, repositório e créditos de dados. */
export function SiteFooter() {
  return (
    <CapywitchSiteFooter>
      <p>
        <span className="font-semibold text-fg">Meus Brackets</span> é uma ferramenta da{" "}
        <FooterLink href="https://tcgrp.com.br">comunidade TCGRP</FooterLink> pra estimar o
        bracket de decks de Commander.
      </p>
      <p>
        Projeto{" "}
        <FooterLink href="https://github.com/capywitch/bracket">open source</FooterLink>,
        contribuições são bem-vindas. Inspirado no projeto original{" "}
        <FooterLink href="https://github.com/QuackQuackLabs/MTG-Analyzer">
          QuackQuackLabs/MTG-Analyzer
        </FooterLink>
        .
      </p>
      <p className="border-t border-white/10 pt-3 text-xs">
        Imagens e dados de cartas © Wizards of the Coast, via{" "}
        <FooterLink href="https://scryfall.com">Scryfall</FooterLink>. Fan content não oficial,
        sem afiliação com a Wizards of the Coast.
      </p>
    </CapywitchSiteFooter>
  );
}
