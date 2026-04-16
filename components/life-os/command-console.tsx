"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CalendarRange, LayoutGrid, Plus, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getAssistantResultCards } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

const SUGGESTED_COMMANDS = [
  "build dashboard",
  "what should i do today",
  "generate weekly plan",
  "rebalance schedule",
  "focus workspace CS 3345",
  "create project orbit launch site",
  "create study session OS quiz review",
  "explain priority",
];

const ACCENT_STYLES = {
  sky: "bg-sky-400/14 text-sky-100 ring-1 ring-sky-300/18",
  violet: "bg-violet-400/14 text-violet-100 ring-1 ring-violet-300/18",
  amber: "bg-amber-400/14 text-amber-100 ring-1 ring-amber-300/18",
  emerald: "bg-emerald-400/14 text-emerald-100 ring-1 ring-emerald-300/18",
  rose: "bg-rose-400/14 text-rose-100 ring-1 ring-rose-300/18",
} as const;

export function CommandConsole({
  embedded = false,
  onComplete,
}: {
  embedded?: boolean;
  onComplete?: () => void;
}) {
  const router = useRouter();
  const { clearCommandResult, lastCommandResult, runCommand } = useLifeOs();
  const [input, setInput] = useState("");
  const quickResults = getAssistantResultCards(lastCommandResult ? [lastCommandResult] : []);

  const executeCommand = (commandText: string) => {
    const trimmed = commandText.trim();
    if (!trimmed) {
      return;
    }

    const result = runCommand(trimmed);
    setInput("");

    if (result.kind === "navigation") {
      router.push(result.href);
    }

    onComplete?.();
  };

  return (
    <div
      className={cn(
        "space-y-3",
        embedded ? "" : "rounded-2xl border hairline bg-[var(--surface-soft)]/72 p-3",
      )}
    >
      <form
        className="space-y-2.5"
        onSubmit={(event) => {
          event.preventDefault();
          executeCommand(input);
        }}
      >
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Run a quick Orbit action"
            className="h-10 rounded-xl border-white/10 bg-background/70 text-[13px] text-foreground"
          />
          <div className="flex items-center gap-2">
            {lastCommandResult ? (
              <Button type="button" variant="outline" size="sm" onClick={clearCommandResult}>
                Clear
              </Button>
            ) : null}
            <Button type="submit" size="sm" className="min-w-[124px]">
              <Sparkles className="size-4" />
              Run command
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {SUGGESTED_COMMANDS.slice(0, 5).map((command) => (
            <Button
              key={command}
              type="button"
              variant="outline"
              size="sm"
              className="h-7 rounded-full px-2.5 text-[11px]"
              onClick={() => executeCommand(command)}
            >
              {command}
            </Button>
          ))}
        </div>
      </form>

      <div className="grid gap-2 sm:grid-cols-3">
        <div className="rounded-xl border hairline bg-background/55 p-3">
          <Plus className="size-3.5 text-primary" />
          <p className="mt-2 text-[12px] font-medium text-foreground">Quick capture</p>
          <p className="mt-1 text-[11px] leading-4 text-muted-foreground">Create tasks, sessions, or projects without leaving the current surface.</p>
        </div>
        <div className="rounded-xl border hairline bg-background/55 p-3">
          <LayoutGrid className="size-3.5 text-primary" />
          <p className="mt-2 text-[12px] font-medium text-foreground">Widget update</p>
          <p className="mt-1 text-[11px] leading-4 text-muted-foreground">Rebuild Home or suggest a tighter dashboard mix from one command.</p>
        </div>
        <div className="rounded-xl border hairline bg-background/55 p-3">
          <CalendarRange className="size-3.5 text-primary" />
          <p className="mt-2 text-[12px] font-medium text-foreground">Schedule move</p>
          <p className="mt-1 text-[11px] leading-4 text-muted-foreground">Jump straight to the calendar when the week needs rebalancing.</p>
        </div>
      </div>

      {quickResults[0] ? (
        <div className="rounded-xl border hairline bg-background/70 p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className={cn("inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.18em]", ACCENT_STYLES[quickResults[0].accent])}>
                {quickResults[0].category}
              </span>
              <p className="mt-2 text-[13px] font-medium text-foreground">{quickResults[0].title}</p>
              <p className="mt-1 text-[12px] leading-5 text-muted-foreground">{quickResults[0].summary}</p>
            </div>
          </div>
          {quickResults[0].lines.length ? (
            <div className="mt-3 space-y-1.5 text-[11px] text-muted-foreground">
              {quickResults[0].lines.slice(0, 3).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          ) : null}
          {quickResults[0].href ? (
            <Link href={quickResults[0].href} className="mt-3 inline-flex text-[11px] font-medium text-primary underline-offset-4 hover:underline">
              Open linked surface
            </Link>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
