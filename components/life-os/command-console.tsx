"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarRange, LayoutGrid, Plus, Sparkles } from "lucide-react";

import { CommandResultView } from "@/components/life-os/command-result-view";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

const SUGGESTED_COMMANDS = [
  "build dashboard",
  "what should i do today",
  "generate weekly plan",
  "rebalance schedule",
  "focus workspace CS 3345",
];

export function CommandConsole({
  embedded = false,
  onComplete,
}: {
  embedded?: boolean;
  onComplete?: () => void;
}) {
  const router = useRouter();
  const {
    clearCommandResult,
    lastCommandResult,
    runCommand,
    applyActiveWeeklyPlan,
    applyScheduleSuggestion,
    dismissScheduleSuggestion,
    focusWorkspace,
  } = useLifeOs();
  const [input, setInput] = useState("");

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
          {SUGGESTED_COMMANDS.map((command) => (
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

      {lastCommandResult ? (
        <CommandResultView
          result={lastCommandResult}
          onPlanApply={() => {
            applyActiveWeeklyPlan();
          }}
          onSuggestionApply={(id) => applyScheduleSuggestion(id)}
          onSuggestionDismiss={(id) => dismissScheduleSuggestion(id)}
          onClearFocus={() => {
            focusWorkspace(null);
            runCommand("clear focus");
          }}
        />
      ) : null}
    </div>
  );
}
