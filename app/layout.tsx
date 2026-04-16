import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { TooltipProvider } from "@/components/ui/tooltip";
import { LifeOsProvider } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const geistHeading = Geist({
  subsets: ["latin"],
  variable: "--font-heading",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Life OS",
  description:
    "A shared operating system for study flows, coursework, life admin, and context-aware planning.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={cn(
        "scroll-smooth",
        geist.variable,
        geistHeading.variable,
        geistMono.variable,
      )}
    >
      <body className="min-h-screen bg-background text-foreground antialiased">
        <TooltipProvider delay={120}>
          <LifeOsProvider>{children}</LifeOsProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}
