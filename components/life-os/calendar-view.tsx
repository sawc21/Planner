"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { CalendarRange, Check, Clock3, Sparkles, X } from "lucide-react";

import { EmptyState } from "@/components/life-os/empty-state";
import { EventCard } from "@/components/life-os/event-card";
import { LifeItemCard } from "@/components/life-os/life-item-card";
import { PageHeader } from "@/components/life-os/page-header";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getAgendaGroups,
  getScheduleRebalanceSummary,
  getTodayRecommendations,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

export function CalendarView() {
  const {
    workspaces,
    tasks,
    events,
    constraintProfile,
    focusTodayIds,
    toggleFocusToday,
    completeTask,
    moveTaskToTomorrow,
    startTask,
    pendingScheduleSuggestions,
    activeWeeklyPlan,
    applyScheduleSuggestion,
    dismissScheduleSuggestion,
  } = useLifeOs();
  const agendaGroups = getAgendaGroups({ workspaces, tasks, events });
  const rebalanceSummary = getScheduleRebalanceSummary(pendingScheduleSuggestions);
  const pendingSuggestions = pendingScheduleSuggestions.filter(
    (entry) => entry.status === "pending",
  );
  const planSteps = activeWeeklyPlan?.steps ?? [];
  const planDayCounts = planSteps.reduce<Map<string, number>>((map, step) => {
    const key = step.scheduledFor.slice(0, 10);
    map.set(key, (map.get(key) ?? 0) + 1);
    return map;
  }, new Map());
  const [selectedKey, setSelectedKey] = useState(agendaGroups[0]?.key ?? "");
  const selectedDay = useMemo(
    () => agendaGroups.find((group) => group.key === selectedKey) ?? agendaGroups[0],
    [agendaGroups, selectedKey],
  );
  const recommendation = getTodayRecommendations({ workspaces, tasks, constraintProfile }).primary;

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Calendar"
        title="Orbit is reading the week as one operating window."
        description="Inspect day pressure, open windows, and the fastest place to absorb study moves or project work without breaking the week."
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.45fr)_300px]">
        <div className="space-y-3">
          <Card className="surface-panel rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Weekly agenda</CardTitle>
              <p className="text-[12px] leading-5 text-muted-foreground">
                Click any day to inspect the load, open windows, and visible commitments.
              </p>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {agendaGroups.map((group) => (
                <button
                  key={group.key}
                  type="button"
                  onClick={() => setSelectedKey(group.key)}
                  className={cn(
                    "w-full rounded-lg border hairline bg-background/62 px-3 py-2.5 text-left transition-colors hover:bg-background/76",
                    selectedDay?.key === group.key && "ring-2 ring-primary/18",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[13px] font-semibold tracking-tight text-foreground">{group.label}</p>
                      <p className="mt-1 text-[11px] text-muted-foreground">{group.pressureLabel}</p>
                    </div>
                    <span className="rounded-md bg-[var(--surface-soft)] px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                      {group.loadPercent}% load
                    </span>
                  </div>
                  <div className="mt-2.5 h-1.5 rounded-full bg-border/70">
                    <div className="h-1.5 rounded-full bg-primary/90" style={{ width: `${group.loadPercent}%` }} />
                  </div>
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {group.openWindows.map((window) => (
                      <span key={window} className="rounded-md bg-[var(--surface-soft)] px-2 py-0.5 text-[10px] text-muted-foreground">
                        {window}
                      </span>
                    ))}
                    {planDayCounts.get(group.key) ? (
                      <span
                        data-testid={`plan-marker-${group.key}`}
                        className="inline-flex items-center gap-1 rounded-md bg-sky-400/12 px-2 py-0.5 text-[10px] text-sky-100"
                      >
                        <span className="size-1.5 rounded-full bg-sky-300" />
                        {planDayCounts.get(group.key)} plan step
                        {(planDayCounts.get(group.key) ?? 0) > 1 ? "s" : ""}
                      </span>
                    ) : null}
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>

          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Schedule action strip</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Link href="/assistant?intent=rebalance_schedule" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                <CalendarRange className="size-4" />
                Rebalance schedule
              </Link>
              <Link href="/assistant?intent=create_study_session" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                <Clock3 className="size-4" />
                Add study session
              </Link>
              <Link href="/assistant?intent=focus_workspace" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                <Sparkles className="size-4" />
                Focus a workspace
              </Link>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-3">
          <Card data-testid="pending-schedule-panel" className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Pending schedule moves</CardTitle>
              <p className="text-[12px] leading-5 text-muted-foreground">
                {rebalanceSummary.pendingCount} pending ·{" "}
                {rebalanceSummary.appliedCount} applied
              </p>
            </CardHeader>
            <CardContent className="space-y-2">
              {pendingSuggestions.length ? (
                pendingSuggestions.map((suggestion) => (
                  <div
                    key={suggestion.id}
                    className="rounded-xl border hairline bg-background/55 px-3 py-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-[12px] font-medium text-foreground">
                          {suggestion.title}
                        </p>
                        <p className="mt-1 text-[11px] leading-4 text-muted-foreground">
                          {suggestion.reason}
                        </p>
                      </div>
                      <Badge
                        variant="outline"
                        className="rounded-full border-amber-300/20 bg-amber-400/10 px-2 py-0.5 text-[10px] text-amber-100"
                      >
                        Pending
                      </Badge>
                    </div>
                    <div className="mt-2 flex gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-full px-3 text-[11px]"
                        onClick={() => applyScheduleSuggestion(suggestion.id)}
                      >
                        <Check className="size-3.5" />
                        Apply
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 rounded-full px-3 text-[11px]"
                        onClick={() => dismissScheduleSuggestion(suggestion.id)}
                      >
                        <X className="size-3.5" />
                        Dismiss
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-[12px] text-muted-foreground">
                  No schedule changes pending. Ask the assistant to rebalance your week.
                </p>
              )}
            </CardContent>
          </Card>

          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Selected day</CardTitle>
              <p className="text-[12px] leading-5 text-muted-foreground">
                {selectedDay ? `${selectedDay.entries.length} visible items and ${selectedDay.openWindows.length} open windows.` : "Pick a day to inspect it."}
              </p>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {selectedDay?.entries.length ? (
                selectedDay.entries.map((entry) =>
                  entry.kind === "event" && entry.event ? (
                    <EventCard key={entry.id} event={entry.event} compact />
                  ) : entry.task ? (
                    <LifeItemCard
                      key={entry.id}
                      compact
                      item={entry.task}
                      onCompleteTask={() => completeTask(entry.task!.id)}
                      onMoveTaskToTomorrow={() => moveTaskToTomorrow(entry.task!.id)}
                      onStartTask={() => startTask(entry.task!.id)}
                      onToggleFocus={() => toggleFocusToday(entry.task!.id)}
                      isFocused={focusTodayIds.includes(entry.task!.id)}
                    />
                  ) : null,
                )
              ) : (
                <EmptyState
                  title="This day is still open"
                  description="Orbit sees enough slack here to absorb a reschedule if the week tightens."
                />
              )}
            </CardContent>
          </Card>

          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Open windows</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {selectedDay?.openWindows.length ? (
                selectedDay.openWindows.map((window) => (
                  <span key={window} className="rounded-full border hairline bg-[var(--surface-soft)] px-2.5 py-0.5 text-[11px] text-muted-foreground">
                    {window}
                  </span>
                ))
              ) : (
                <p className="text-[12px] text-muted-foreground">No clear open windows are visible on this day.</p>
              )}
            </CardContent>
          </Card>

          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Orbit suggestion</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-[12px] leading-5 text-muted-foreground">
                {recommendation
                  ? `If the week starts widening, keep ${recommendation.item.title.toLowerCase()} as the anchor before you move anything else.`
                  : "The schedule is calm enough that you can preserve open time on purpose."}
              </p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

