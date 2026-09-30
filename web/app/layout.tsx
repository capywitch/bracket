import type { Metadata } from "next";
import { openSans } from "@capywitch/ui/fonts";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: "Meus Brackets: Analista de Bracket da TCGRP",
  description: "Descubra o nível de poder do seu deck de Commander e o que ajustar nele.",
  metadataBase: new URL("https://bracket.tcgrp.com.br"),
  openGraph: {
    title: "Meus Brackets: Analista de Bracket da TCGRP",
    description: "Descubra o nível de poder do seu deck de Commander e o que ajustar nele.",
    url: "https://bracket.tcgrp.com.br",
    siteName: "Meus Brackets",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Meus Brackets Capywitch",
      },
    ],
    locale: "pt_BR",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Meus Brackets: Analista de Bracket da TCGRP",
    description: "Descubra o nível de poder do seu deck de Commander e o que ajustar nele.",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={openSans.variable}>
      <body className="flex min-h-screen flex-col bg-bg font-sans text-fg antialiased">
        <SiteHeader />
        <div className="flex-1">{children}</div>
        <SiteFooter />
      </body>
    </html>
  );
}
