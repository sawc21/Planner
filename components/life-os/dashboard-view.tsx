"use client";

import Link from "next/link";
import { format } from "date-fns";
import { AlertCircle, CalendarClock, Sparkles, TrendingUp } from "lucide-react";

import { BuddyPanel } from "@/components/life-os/buddy-panel";
import { ConstraintCard } from "@/components/life-os/constraint-card";
import { EmptyState } from "@/components/life-os/empty-state";
import { EventCard } from "@/components/life-os/event-card";
import { LifeItemCard } from "@/components/life-os/life-item-card";
import { MetricCard } from "@/components/life-os/metric-card";
import { OverloadWarningCard } from "@/components/life-os/overload-warning-card";
import { PageHeader } from "@/components/life-os/page-header";
import { RecommendationCard } from "@/components/life-os/recommendation-card";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  buildDailyNarrative,
  getAgendaGroups,
  getAtRiskWorkspaces,
  getBuddyInsight,
  getConstraintAwarePlan,
  getOverloadAssessment,
  getTodayRecommendations,
  getTodayTasks,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

export function DashboardView() {
  const {
    workspaces,
    tasks,
    events,
    gradebooks,
    progressRecords,
    constraintProfile,
    focusTodayIds,
    toggleFocusToday,
    completeTask,
    moveTaskToTomorrow,
    startTask,
  } = useLifeOs();

  const recommendations = getTodayRecommendations({
    workspaces,
    tasks,
    constraintProfile,
  });
  const overload = getOverloadAssessment({
    workspaces,
    tasks,
    constraintProfile,
  });
  const atRisk = getAtRiskWorkspaces({
    workspaces,
    tasks,
    gradebooks,
    progressRecords,
  });
  const agenda = getAgendaGroups({ workspaces, tasks, events });
  const todayGroup = agenda[0];
  const todayTasks = getTodayTasks({ workspaces, tasks });
  const buddyInsight = getBuddyInsight({
    workspaces,
    tasks,
    constraintProfile,
    gradebooks,
    progressRecords,
  });
  const plan = getConstraintAwarePlan({
    workspaces,
    tasks,
    constraintProfile,
    gradebooks,
    progressRecords,
  });
  const narrative = buildDailyNarrative({
    workspaces,
    tasks,
    constraintProfile,
    gradebooks,
    progressRecords,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Today"
        title="A shared operating system for the day."
        description="Life admin, coursework, and self-directed study all live on one board, with context-aware planning deciding what should move first."
      />

      <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="surface-panel overflow-hidden rounded-2xl border-none">
          <CardContent className="space-y-6 p-6">
            <div className="space-y-2">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
                {format(new Date(), "EEEE, MMMM d")}
              </p>
              <h2 className="text-3xl font-semibold tracking-tight text-foreground">
                What deserves your calm attention first?
              </h2>
              <p className="max-w-2xl text-[13px] leading-5 text-muted-foreground">
                The board knows what class, study track, or life flow each item belongs to, so the
                recommendation can weigh urgency, grade pressure, momentum, and constraints at the
                same time.
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <MetricCard
                label="Today"
                value={String(todayTasks.length)}
                detail="Open tasks touching today"
                icon={CalendarClock}
              />
              <MetricCard
                label="At risk"
                value={String(atRisk.length)}
                detail="Workspaces asking for attention"
                icon={AlertCircle}
              />
              <MetricCard
                label="Focus"
                value={String(focusTodayIds.length)}
                detail="Tasks you've marked to protect"
                icon={Sparkles}
              />
            </div>

            <div className="rounded-xl border hairline bg-card/70 p-4">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Narrative summary
              </p>
              <p className="mt-2 text-[13px] leading-6 text-foreground/85">{narrative}</p>
            </div>
          </CardContent>
        </Card>

        <RecommendationCard
          recommendations={recommendations}
          onCompleteTask={completeTask}
          onMoveTaskToTomorrow={moveTaskToTomorrow}
          onStartTask={startTask}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-4">
          <OverloadWarningCard assessment={overload} />
          <ConstraintCard constraintProfile={constraintProfile} />
          <BuddyPanel insight={buddyInsight} plan={plan} />
        </div>

        <div className="space-y-4">
          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle className="text-xl font-semibold tracking-tight">
                  Today&apos;s schedule
                </CardTitle>
                <p className="mt-1.5 text-[13px] leading-5 text-muted-foreground">
                  Events and due work grouped together so the study flow and the life flow stay in
                  the same view.
                </p>
              </div>
              <Link href="/agenda" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                Open agenda
              </Link>
            </CardHeader>
            <CardContent className="space-y-3">
              {todayGroup?.entries.length ? (
                todayGroup.entries.slice(0, 5).map((entry) =>
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
                  icon={CalendarClock}
                  title="Today still has breathing room"
                  description="No tasks or events are currently tied to today."
                />
              )}
            </CardContent>
          </Card>

          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle className="text-xl font-semibold tracking-tight">
                  At-risk workspaces
                </CardTitle>
                <p className="mt-1.5 text-[13px] leading-5 text-muted-foreground">
                  The contexts most likely to slip next, whether they are classes, study tracks, or
                  life admin.
                </p>
              </div>
              <Link href="/workspaces?view=at-risk" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                Open workspaces
              </Link>
            </CardHeader>
            <CardContent className="space-y-2">
              {atRisk.length ? (
                atRisk.map((risk) => (
                  <Link
                    key={risk.workspace.id}
                    href={`/workspaces/${risk.workspace.id}`}
                    className="block rounded-lg border hairline bg-card/80 p-3.5 transition-transform hover:-translate-y-0.5"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-[13px] font-medium text-foreground">
                          {risk.workspace.name}
                        </p>
                        <p className="mt-1 text-[12px] text-muted-foreground">{risk.reason}</p>
                      </div>
                      <span className="rounded-md border hairline bg-[var(--surface-soft)] px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
                        {risk.workspace.shortLabel}
                      </span>
                    </div>
                  </Link>
                ))
              ) : (
                <EmptyState
                  icon={TrendingUp}
                  title="No workspace is clearly slipping"
                  description="The current mix of coursework, study tracks, and life admin still looks stable."
                />
              )}
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
