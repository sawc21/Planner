"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { formatDistanceToNowStrict } from "date-fns";
import { CalendarRange, Command, LayoutGrid, Sparkles, X } from "lucide-react";

import { CommandResultView } from "@/components/life-os/command-result-view";
import { PageHeader } from "@/components/life-os/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  getFocusedWorkspaceStatus,
  getRecentAssistantActivity,
  getScheduleRebalanceSummary,
  getWeeklyPlanSummary,
} from "@/lib/life-os/selectors";
import type { AssistantActivityEvent, AssistantActivitySurface } from "@/lib/life-os/types";
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

const SURFACE_LABELS: Record<AssistantActivitySurface, string> = {
  home: "Home",
  calendar: "Calendar",
  workspaces: "Workspaces",
  assignments: "Assignments",
  grades: "Grades",
  assistant: "Assistant",
};

export function CommandCenterView() {
  const router = useRouter();
  const {
    workspaces,
    tasks,
    commandHistory,
    lastCommandResult,
    clearCommandResult,
    runCommand,
    activeWeeklyPlan,
    pendingScheduleSuggestions,
    assistantActivity,
    focusedWorkspaceId,
    applyActiveWeeklyPlan,
    applyScheduleSuggestion,
    dismissScheduleSuggestion,
    focusWorkspace,
    markActivityRead,
  } = useLifeOs();
  const [input, setInput] = useState("");

  const resultStack = useMemo(() => {
    const items = lastCommandResult ? [lastCommandResult, ...commandHistory.slice(1)] : commandHistory;
    return items.slice(0, 8);
  }, [commandHistory, lastCommandResult]);

  const planSummary = getWeeklyPlanSummary(activeWeeklyPlan);
  const rebalanceSummary = getScheduleRebalanceSummary(pendingScheduleSuggestions);
  const focusStatus = getFocusedWorkspaceStatus(focusedWorkspaceId, workspaces, tasks);
  const activityFeed = getRecentAssistantActivity(assistantActivity, 12);

  const hasActiveState =
    Boolean(planSummary) || rebalanceSummary.pendingCount > 0 || Boolean(focusStatus?.workspace);

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

  const handleClearFocus = () => {
    focusWorkspace(null);
    runCommand("clear focus");
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

      {hasActiveState ? (
        <div
          data-testid="active-state-strip"
          className="flex flex-wrap items-center gap-2 rounded-2xl border hairline bg-background/55 px-3 py-2"
        >
          {planSummary ? (
            <div
              data-testid="assistant-active-plan"
              className="inline-flex items-center gap-2 rounded-full border hairline bg-sky-400/10 px-3 py-1 text-[11px] text-foreground"
            >
              <Sparkles className="size-3.5 text-sky-300" />
              <span>
                Active plan · {planSummary.appliedCount}/{planSummary.totalSteps} applied
              </span>
              {planSummary.appliedCount < planSummary.totalSteps ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-6 rounded-full px-2 text-[11px]"
                  onClick={() => applyActiveWeeklyPlan()}
                >
                  Apply
                </Button>
              ) : null}
            </div>
          ) : null}
          {rebalanceSummary.pendingCount > 0 ? (
            <div
              data-testid="assistant-pending-moves"
              className="inline-flex items-center gap-2 rounded-full border hairline bg-amber-400/10 px-3 py-1 text-[11px] text-foreground"
            >
              <CalendarRange className="size-3.5 text-amber-300" />
              <span>
                {rebalanceSummary.pendingCount} pending schedule move
                {rebalanceSummary.pendingCount === 1 ? "" : "s"}
              </span>
              <Link
                href="/calendar"
                className="text-[11px] font-medium text-primary underline-offset-4 hover:underline"
              >
                Review
              </Link>
            </div>
          ) : null}
          {focusStatus?.workspace ? (
            <div
              data-testid="assistant-focused-workspace"
              className="inline-flex items-center gap-2 rounded-full border hairline bg-emerald-400/10 px-3 py-1 text-[11px] text-foreground"
            >
              <Badge
                variant="outline"
                className="rounded-full border-emerald-300/20 bg-emerald-400/10 px-2 py-0.5 text-[10px] text-emerald-100"
              >
                Focused
              </Badge>
              <span>{focusStatus.workspace.shortLabel}</span>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-6 rounded-full px-2 text-[11px]"
                onClick={handleClearFocus}
              >
                <X className="size-3.5" />
                Clear
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

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

          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Structured result stack</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {resultStack.length ? (
                resultStack.map((result, index) => (
                  <div
                    key={`${result.kind}-${index}`}
                    data-testid={`result-stack-item-${index}`}
                  >
                    <CommandResultView
                      result={result}
                      onPlanApply={() => {
                        applyActiveWeeklyPlan();
                      }}
                      onSuggestionApply={(id) => applyScheduleSuggestion(id)}
                      onSuggestionDismiss={(id) => dismissScheduleSuggestion(id)}
                      onClearFocus={handleClearFocus}
                    />
                  </div>
                ))
              ) : (
                <div className="rounded-xl border hairline bg-background/52 p-3 text-[12px] text-muted-foreground">
                  Run a command to start a persistent Orbit result stack.
                </div>
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

        <aside className="space-y-3">
          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Current focus</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[12px] text-muted-foreground">
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

          <Card data-testid="activity-pane" className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Activity</CardTitle>
              <p className="text-[11px] leading-4 text-muted-foreground">
                Orbit receipts, plans, and schedule moves land here first.
              </p>
            </CardHeader>
            <CardContent className="space-y-2">
              {activityFeed.length ? (
                activityFeed.map((entry) => (
                  <ActivityRow
                    key={entry.id}
                    entry={entry}
                    onClick={() => markActivityRead(entry.id)}
                  />
                ))
              ) : (
                <p className="text-[12px] text-muted-foreground">No assistant activity yet.</p>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function ActivityRow({
  entry,
  onClick,
}: {
  entry: AssistantActivityEvent;
  onClick: () => void;
}) {
  const href = entry.href ?? "/assistant";
  return (
    <Link
      data-testid={`activity-row-${entry.id}`}
      data-read={entry.read ? "true" : "false"}
      href={href}
      onClick={onClick}
      className={cn(
        "block rounded-lg border hairline px-3 py-2 text-[11px] transition-colors",
        entry.read
          ? "bg-background/40 text-muted-foreground hover:bg-background/60"
          : "bg-[var(--surface-soft)]/88 text-foreground hover:bg-[var(--surface-soft)]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-foreground">{entry.title}</p>
          <p className="mt-1 text-[11px] leading-4 text-muted-foreground">{entry.summary}</p>
        </div>
        <span className="shrink-0 text-[10px] text-muted-foreground/70">
          {formatDistanceToNowStrict(new Date(entry.at), { addSuffix: true })}
        </span>
      </div>
      {entry.affectedSurfaces.length ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {entry.affectedSurfaces.map((surface) => (
            <span
              key={surface}
              className="rounded-full border hairline bg-background/40 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.14em] text-muted-foreground/80"
            >
              {SURFACE_LABELS[surface]}
            </span>
          ))}
        </div>
      ) : null}
    </Link>
  );
}
