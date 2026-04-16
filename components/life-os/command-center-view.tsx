"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, CalendarRange, Command, LayoutGrid, Sparkles } from "lucide-react";

import { PageHeader } from "@/components/life-os/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getAssistantResultCards } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

const PRIMARY_COMMANDS = [
  "build dashboard",
  "generate weekly plan",
  "rebalance schedule",
  "focus workspace CS 3345",
  "explain priority",
];

const NEXT_ACTIONS = [
  {
    label: "Create project",
    command: "create project orbit launch site",
    detail: "Spin up a new side-work board and attach it to the assistant flow.",
  },
  {
    label: "Create study session",
    command: "create study session OS quiz review",
    detail: "Drop a study block straight onto the board and let Orbit route it.",
  },
  {
    label: "What should I do?",
    command: "what should i do today",
    detail: "Explain the next best move with explicit reasoning.",
  },
];

const CATEGORY_STYLES = {
  sky: "bg-sky-400/14 text-sky-100 ring-1 ring-sky-300/16",
  violet: "bg-violet-400/14 text-violet-100 ring-1 ring-violet-300/16",
  amber: "bg-amber-400/14 text-amber-100 ring-1 ring-amber-300/16",
  emerald: "bg-emerald-400/14 text-emerald-100 ring-1 ring-emerald-300/16",
  rose: "bg-rose-400/14 text-rose-100 ring-1 ring-rose-300/16",
} as const;

export function CommandCenterView() {
  const router = useRouter();
  const { commandHistory, lastCommandResult, clearCommandResult, runCommand } = useLifeOs();
  const [input, setInput] = useState("");
  const results = useMemo(
    () => getAssistantResultCards(lastCommandResult ? [lastCommandResult, ...commandHistory.slice(1)] : commandHistory),
    [commandHistory, lastCommandResult],
  );
  const latest = results[0];
  const receipts = results.filter((entry) => entry.lines.length > 0).slice(0, 4);

  const executeCommand = (command: string) => {
    const trimmed = command.trim();
    if (!trimmed) {
      return;
    }

    const result = runCommand(trimmed);
    setInput("");

    if (result.kind === "navigation") {
      router.push(result.href);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Assistant"
        title="Use Orbit as the system control room."
        description="Run commands, inspect structured results, and watch Orbit update plans, routes, and dashboard surfaces in one place."
        actions={
          <Button variant="outline" size="sm" onClick={clearCommandResult}>
            Clear last result
          </Button>
        }
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.45fr)_360px]">
        <div className="space-y-3">
          <Card className="surface-panel rounded-2xl border-none">
            <CardContent className="space-y-3 p-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Command input bar
                  </p>
                  <p className="mt-1 text-[13px] text-foreground/78">
                    Every command returns an action, plan, receipt, navigation, or explanation. Nothing here is decorative.
                  </p>
                </div>
                <span className="rounded-full border hairline bg-background/60 px-2.5 py-1 text-[11px] text-muted-foreground">
                  Dedicated assistant workbench
                </span>
              </div>

              <form
                className="space-y-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  executeCommand(input);
                }}
              >
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Input
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    placeholder="Run Orbit: build dashboard"
                    className="h-11 rounded-xl border-white/10 bg-background/72 text-[13px]"
                  />
                  <Button type="submit" className="min-w-[148px]">
                    <Sparkles className="size-4" />
                    Run command
                  </Button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {PRIMARY_COMMANDS.map((command) => (
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
            </CardContent>
          </Card>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
            <Card className="surface-card rounded-xl border hairline">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-semibold tracking-tight">Structured result stack</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {results.length ? (
                  results.map((result) => (
                    <div key={result.id} className="rounded-xl border hairline bg-background/62 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <span className={cn("inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.16em]", CATEGORY_STYLES[result.accent])}>
                            {result.category}
                          </span>
                          <p className="mt-2 text-[13px] font-medium text-foreground">{result.title}</p>
                          <p className="mt-1 text-[12px] leading-5 text-muted-foreground">{result.summary}</p>
                        </div>
                        {result.href ? <ArrowRight className="mt-1 size-4 text-muted-foreground" /> : null}
                      </div>
                      {result.lines.length ? (
                        <div className="mt-3 grid gap-1.5 text-[11px] text-muted-foreground">
                          {result.lines.slice(0, 4).map((line) => (
                            <p key={line}>{line}</p>
                          ))}
                        </div>
                      ) : null}
                      {result.href ? (
                        <Link href={result.href} className="mt-3 inline-flex text-[11px] font-medium text-primary underline-offset-4 hover:underline">
                          Open linked surface
                        </Link>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl border hairline bg-background/52 p-3 text-[12px] text-muted-foreground">
                    Run a command to start a persistent Orbit result stack.
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="space-y-3">
              <Card className="surface-card rounded-xl border hairline">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg font-semibold tracking-tight">Action receipts</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2.5">
                  {receipts.length ? (
                    receipts.map((receipt) => (
                      <div key={receipt.id} className="rounded-xl border hairline bg-[var(--surface-soft)]/82 p-3">
                        <p className="text-[12px] font-medium text-foreground">{receipt.title}</p>
                        <div className="mt-2 space-y-1 text-[11px] text-muted-foreground">
                          {receipt.lines.slice(0, 3).map((line) => (
                            <p key={line}>{line}</p>
                          ))}
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-[12px] text-muted-foreground">Receipts appear here as Orbit changes the board.</p>
                  )}
                </CardContent>
              </Card>

              <Card className="surface-card rounded-xl border hairline">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg font-semibold tracking-tight">Suggested next actions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2.5">
                  {NEXT_ACTIONS.map((action) => (
                    <button
                      key={action.command}
                      type="button"
                      onClick={() => executeCommand(action.command)}
                      className="block w-full rounded-xl border hairline bg-background/62 p-3 text-left transition-colors hover:bg-background/76"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-[12px] font-medium text-foreground">{action.label}</p>
                          <p className="mt-1 text-[11px] leading-4 text-muted-foreground">{action.detail}</p>
                        </div>
                        <Command className="size-4 text-muted-foreground" />
                      </div>
                    </button>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>
        </div>

        <aside className="space-y-3">
          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Current focus</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[12px] text-muted-foreground">
              <div className="rounded-xl border hairline bg-background/62 p-3">
                <p className="font-medium text-foreground">{latest?.title ?? "Orbit standby"}</p>
                <p className="mt-1 leading-5">{latest?.summary ?? "Run a command to build the first active result."}</p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
                <div className="rounded-xl border hairline bg-background/55 p-3">
                  <LayoutGrid className="size-3.5 text-primary" />
                  <p className="mt-2 text-[12px] font-medium text-foreground">Dashboard control</p>
                  <p className="mt-1 text-[11px] leading-4 text-muted-foreground">Use the assistant to rebuild Home rather than manually managing widgets.</p>
                </div>
                <div className="rounded-xl border hairline bg-background/55 p-3">
                  <CalendarRange className="size-3.5 text-primary" />
                  <p className="mt-2 text-[12px] font-medium text-foreground">Schedule moves</p>
                  <p className="mt-1 text-[11px] leading-4 text-muted-foreground">Rebalance actions stay visible as routes and receipts, not hidden chat text.</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Recent history</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {results.length ? (
                results.slice(0, 6).map((result) => (
                  <div key={`${result.id}-history`} className="rounded-lg border hairline bg-background/55 px-3 py-2">
                    <p className="text-[11px] font-medium text-foreground">{result.category}</p>
                    <p className="mt-1 text-[11px] leading-4 text-muted-foreground">{result.title}</p>
                  </div>
                ))
              ) : (
                <p className="text-[12px] text-muted-foreground">No command history yet.</p>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
