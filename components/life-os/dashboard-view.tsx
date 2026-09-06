"use client";

import Link from "next/link";
import { format, formatDistanceToNowStrict } from "date-fns";
import { ArrowRight, CalendarClock, LayoutGrid, Sparkles, X } from "lucide-react";

import { BuddyPanel } from "@/components/life-os/buddy-panel";
import { ConstraintCard } from "@/components/life-os/constraint-card";
import { OverloadWarningCard } from "@/components/life-os/overload-warning-card";
import { PageHeader } from "@/components/life-os/page-header";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  buildDailyNarrative,
  getBuddyInsight,
  getConstraintAwarePlan,
  getFocusedWorkspaceStatus,
  getHomeBriefingItems,
  getHomeWidgetData,
  getOverloadAssessment,
  getRecentAssistantActivity,
  getTodayRecommendations,
  getWeeklyPlanSummary,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

const ACCENT_STYLES = {
  violet: "bg-violet-400/14 text-violet-100 ring-1 ring-violet-300/16",
  sky: "bg-sky-400/14 text-sky-100 ring-1 ring-sky-300/16",
  amber: "bg-amber-400/14 text-amber-100 ring-1 ring-amber-300/16",
  emerald: "bg-emerald-400/14 text-emerald-100 ring-1 ring-emerald-300/16",
  rose: "bg-rose-400/14 text-rose-100 ring-1 ring-rose-300/16",
} as const;

export function DashboardView() {
  const {
    workspaces,
    tasks,
    events,
    materials,
    milestones,
    widgets,
    gradebooks,
    constraintProfile,
    commandHistory,
    assistantActivity,
    activeWeeklyPlan,
    focusedWorkspaceId,
    completeTask,
    moveTaskToTomorrow,
    startTask,
    openCommandPanel,
    focusWorkspace,
    runCommand,
  } = useLifeOs();

  const snapshot = {
    workspaces,
    tasks,
    events,
    materials,
    milestones,
    widgets,
    gradebooks,
    constraintProfile,
  };
  const recommendations = getTodayRecommendations({ workspaces, tasks, constraintProfile });
  const primary = recommendations.primary;
  const overload = getOverloadAssessment({ workspaces, tasks, constraintProfile });
  const buddyInsight = getBuddyInsight(snapshot);
  const plan = getConstraintAwarePlan({ workspaces, tasks, constraintProfile });
  const narrative = buildDailyNarrative(snapshot);
  const activityFeed = getRecentAssistantActivity(assistantActivity, 5);
  const briefings = activityFeed.length
    ? []
    : getHomeBriefingItems(commandHistory).slice(0, 3);
  const widgetData = getHomeWidgetData(snapshot).filter(
    (entry) => entry.widget.kind !== "primary_recommendation",
  );
  const planSummary = getWeeklyPlanSummary(activeWeeklyPlan);
  const focusStatus = getFocusedWorkspaceStatus(focusedWorkspaceId, workspaces, tasks);

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Home"
        title="Orbit is briefing the system state."
        description="Home is the assistant-created board for priorities, pressure, project motion, and the latest system changes."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={openCommandPanel}>
              Quick run
            </Button>
            <Link href="/assistant" className={cn(buttonVariants({ size: "sm" }))}>
              <Sparkles className="size-4" />
              Open Assistant
            </Link>
          </div>
        }
      />

      {planSummary || focusStatus ? (
        <div className="flex flex-wrap items-center gap-2">
          {planSummary ? (
            <div
              data-testid="active-plan-chip"
              className="inline-flex items-center gap-2 rounded-full border hairline bg-sky-400/10 px-3 py-1 text-[11px] text-foreground"
            >
              <Sparkles className="size-3.5 text-sky-300" />
              <span>
                Active weekly plan · {planSummary.appliedCount}/{planSummary.totalSteps} applied · {planSummary.totalMinutes}m
              </span>
              <Link
                href="/assistant"
                className="text-[11px] font-medium text-primary underline-offset-4 hover:underline"
              >
                View
              </Link>
            </div>
          ) : null}
          {focusStatus && focusStatus.workspace ? (
            <div
              data-testid="focused-workspace-chip"
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
                onClick={() => {
                  focusWorkspace(null);
                  runCommand("clear focus");
                }}
              >
                <X className="size-3.5" />
                Clear
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      <Card className="surface-panel rounded-2xl border-none">
        <CardContent className="grid gap-3 p-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
          <div className="rounded-xl border hairline bg-background/58 p-4">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Current recommendation · {format(new Date(), "EEE, MMM d")}
            </p>
            <p className="mt-2 text-xl font-semibold tracking-tight text-foreground">
              {primary?.item.title ?? "Protect open space"}
            </p>
            <p className="mt-2 text-[12px] leading-5 text-foreground/78">
              {primary?.explanation ?? "Nothing urgent is pressing right now."}
            </p>
            {primary?.scoreBreakdown.length ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {primary.scoreBreakdown.slice(0, 3).map((signal) => (
                  <span key={signal} className="rounded-full border hairline bg-[var(--surface-soft)] px-2 py-0.5 text-[10px] text-muted-foreground">
                    {signal}
                  </span>
                ))}
              </div>
            ) : null}
            {primary ? (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" onClick={() => startTask(primary.item.id)}>
                  Start now
                </Button>
                <Button size="sm" variant="outline" onClick={() => moveTaskToTomorrow(primary.item.id)}>
                  Tomorrow
                </Button>
                <Button size="sm" variant="outline" onClick={() => completeTask(primary.item.id)}>
                  Done
                </Button>
              </div>
            ) : null}
          </div>

          <div className="rounded-xl border hairline bg-background/58 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  What changed
                </p>
                <p className="mt-1 text-[12px] text-foreground/78">Orbit receipts and system updates land here first.</p>
              </div>
              <Link href="/assistant" className="text-[11px] font-medium text-primary underline-offset-4 hover:underline">
                Open workbench
              </Link>
            </div>
            <div data-testid="activity-strip" className="mt-3 grid gap-2">
              {activityFeed.length ? (
                activityFeed.map((entry) => (
                  <Link
                    key={entry.id}
                    href={entry.href ?? "/assistant"}
                    className="rounded-lg border hairline bg-[var(--surface-soft)]/88 px-3 py-2 text-[11px] text-muted-foreground transition-colors hover:bg-[var(--surface-soft)]"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className="font-medium text-foreground">{entry.title}</span>
                        <span className="mx-1 text-muted-foreground/70">·</span>
                        {entry.summary}
                      </div>
                      <span className="shrink-0 text-[10px] text-muted-foreground/70">
                        {formatDistanceToNowStrict(new Date(entry.at), { addSuffix: true })}
                      </span>
                    </div>
                    {entry.affectedSurfaces.length ? (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {entry.affectedSurfaces.slice(0, 3).map((surface) => (
                          <span
                            key={surface}
                            className="rounded-full border hairline bg-background/40 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.14em] text-muted-foreground/80"
                          >
                            {surface}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </Link>
                ))
              ) : briefings.length ? (
                briefings.map((item) => (
                  <Link
                    key={item.id}
                    href={item.href ?? "/assistant"}
                    className="rounded-lg border hairline bg-[var(--surface-soft)]/88 px-3 py-2 text-[11px] text-muted-foreground transition-colors hover:bg-[var(--surface-soft)]"
                  >
                    <span className="font-medium text-foreground">{item.label}</span>
                    <span className="mx-1 text-muted-foreground/70">·</span>
                    {item.summary}
                  </Link>
                ))
              ) : (
                <p className="rounded-lg border hairline bg-[var(--surface-soft)]/88 px-3 py-2 text-[11px] text-muted-foreground">
                  No assistant receipts yet. Run a command from the assistant to start building the board history.
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.5fr)_320px]">
        <div className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            {widgetData.map((entry) => {
              const href =
                entry.widget.kind === "assistant_summary" || entry.widget.kind === "quick_actions"
                  ? "/assistant"
                  : entry.widget.href;

              return (
                <Link
                  key={entry.widget.id}
                  href={href}
                  className={cn(
                    "surface-card rounded-xl border hairline p-3.5 transition-transform duration-150 hover:-translate-y-0.5",
                    entry.widget.layout === "wide" ? "md:col-span-2 xl:col-span-3" : "xl:col-span-2",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className={cn("inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.16em]", ACCENT_STYLES[entry.widget.accent])}>
                      {entry.accentLabel}
                    </span>
                    <LayoutGrid className="size-3.5 text-muted-foreground" />
                  </div>
                  <h3 className="mt-3 text-[15px] font-semibold tracking-tight text-foreground">{entry.headline}</h3>
                  <p className="mt-1.5 text-[12px] leading-5 text-muted-foreground">{entry.detail}</p>
                  {entry.stats.length ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {entry.stats.map((stat) => (
                        <span key={stat} className="rounded-full border hairline bg-[var(--surface-soft)] px-2 py-0.5 text-[10px] text-muted-foreground">
                          {stat}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </Link>
              );
            })}
          </div>
        </div>

        <aside className="space-y-3">
          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Briefing summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5 text-[12px] leading-5 text-muted-foreground">
              <p>{narrative}</p>
              <div className="rounded-xl border hairline bg-[var(--surface-soft)]/86 p-3">
                <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-foreground/82">Assistant route</p>
                <p className="mt-1 text-[11px] text-muted-foreground">Use `/assistant` for widget rebuilds, plans, receipts, and schedule control.</p>
              </div>
            </CardContent>
          </Card>

          <OverloadWarningCard assessment={overload} />
          <BuddyPanel insight={buddyInsight} plan={plan} />
          <ConstraintCard constraintProfile={constraintProfile} />

          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Quick actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Link href="/assistant" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-full justify-start")}>
                <Sparkles className="size-4" />
                Open assistant workbench
              </Link>
              <Link href="/calendar?view=rebalance" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-full justify-start")}>
                <CalendarClock className="size-4" />
                Rebalance schedule
              </Link>
              <Link href="/assignments?scope=overdue" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-full justify-start")}>
                <ArrowRight className="size-4" />
                Open urgent assignments
              </Link>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
