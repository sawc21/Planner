"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarRange, Layers3, Plus, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLifeOs } from "@/lib/life-os/state";

const SUGGESTED_COMMANDS = [
  "add task finish OS lab write-up",
  "add event advisor check-in",
  "add material interview notes",
  "create workspace spanish writing sprint",
  "what should i do today",
  "build study flow",
  "show at-risk workspaces",
  "rebalance week",
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
  } = useLifeOs();
  const [input, setInput] = useState("");

  const handleSubmit = (commandText: string) => {
    const result = runCommand(commandText);

    if (result.kind === "navigation") {
      router.push(result.href);
      onComplete?.();
      setInput("");
      return;
    }

    if (result.kind === "mutation") {
      setInput("");
    }
  };

  return (
    <div className={`space-y-5 ${embedded ? "" : "rounded-[28px] bg-[var(--surface-soft)] p-4"}`}>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          handleSubmit(input);
        }}
      >
        <Input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Try: build study flow"
          className="h-12 rounded-2xl bg-white/70 text-foreground"
        />
        <div className="flex flex-wrap gap-2">
          {SUGGESTED_COMMANDS.map((command) => (
            <Button
              key={command}
              type="button"
              variant="outline"
              size="sm"
              className="rounded-full"
              onClick={() => {
                setInput(command);
                handleSubmit(command);
              }}
            >
              {command}
            </Button>
          ))}
        </div>
        <div className="flex items-center justify-end gap-2">
          {lastCommandResult ? (
            <Button type="button" variant="outline" onClick={clearCommandResult}>
              Clear
            </Button>
          ) : null}
          <Button type="submit">
            <Sparkles className="size-4" />
            Run command
          </Button>
        </div>
      </form>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl bg-white/80 p-4">
          <Plus className="size-4 text-primary" />
          <p className="mt-2 font-medium text-foreground">Quick capture</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Add tasks, events, materials, or whole new workspaces in one line.
          </p>
        </div>
        <div className="rounded-2xl bg-white/80 p-4">
          <Sparkles className="size-4 text-primary" />
          <p className="mt-2 font-medium text-foreground">Ask for the next move</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Pull today&apos;s recommendation or a full study flow without leaving the screen.
          </p>
        </div>
        <div className="rounded-2xl bg-white/80 p-4">
          <CalendarRange className="size-4 text-primary" />
          <p className="mt-2 font-medium text-foreground">Rebalance the week</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Jump straight to agenda or workspace triage when the week starts to widen.
          </p>
        </div>
      </div>

      {lastCommandResult ? (
        <div className="rounded-[24px] border hairline bg-white/80 p-4">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Result
          </p>
          <p className="mt-2 font-medium text-foreground">{lastCommandResult.message}</p>
          {lastCommandResult.kind === "recommendation" && lastCommandResult.recommendation ? (
            <div className="mt-3 rounded-2xl bg-[var(--surface-soft)] p-3">
              <p className="font-medium text-foreground">
                {lastCommandResult.recommendation.item.title}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {lastCommandResult.recommendation.explanation}
              </p>
            </div>
          ) : null}
          {lastCommandResult.kind === "plan" ? (
            <div className="mt-3 space-y-3">
              <div className="rounded-2xl bg-[var(--surface-soft)] p-3">
                <p className="font-medium text-foreground">{lastCommandResult.plan.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {lastCommandResult.plan.summary}
                </p>
              </div>
              {lastCommandResult.plan.steps.map((step) => (
                <div key={step.id} className="rounded-2xl bg-[var(--surface-soft)] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-foreground">{step.title}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{step.reason}</p>
                    </div>
                    <span className="rounded-full bg-white/80 px-3 py-1 text-xs text-muted-foreground">
                      {step.minutes} min
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {lastCommandResult.kind === "mutation" ? (
            <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs text-muted-foreground">
              <Layers3 className="size-3.5" />
              The shared workspace model updated locally.
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
