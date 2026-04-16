import type { Metadata } from "next";
import { Fraunces, Manrope } from "next/font/google";

import { TooltipProvider } from "@/components/ui/tooltip";
import { LifeOsProvider } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-heading",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Life OS",
  description: "A calm planning cockpit for the week ahead.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={cn("scroll-smooth", manrope.variable, fraunces.variable)}
    >
      <body className="min-h-screen bg-background text-foreground antialiased">
        <TooltipProvider delay={120}>
          <LifeOsProvider>{children}</LifeOsProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}
