"use client";

import Link from "next/link";
import { Sigma, Target, TrendingUp } from "lucide-react";

import { BuddyPanel } from "@/components/life-os/buddy-panel";
import { EmptyState } from "@/components/life-os/empty-state";
import { PageHeader } from "@/components/life-os/page-header";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getBuddyInsight,
  getConstraintAwarePlan,
  getGradeWhatIfCards,
  getProgressCards,
  getSemesterGpaSnapshot,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

export function ProgressView() {
  const { workspaces, tasks, events, materials, milestones, widgets, gradebooks, constraintProfile } = useLifeOs();
  const { courseCards } = getProgressCards({ workspaces, tasks, gradebooks, milestones });
  const whatIfCards = getGradeWhatIfCards({ workspaces, gradebooks });
  const semester = getSemesterGpaSnapshot({ workspaces, gradebooks });
  const buddyInsight = getBuddyInsight({
    workspaces,
    tasks,
    events,
    materials,
    milestones,
    widgets,
    constraintProfile,
    gradebooks,
  });
  const plan = getConstraintAwarePlan({ workspaces, tasks, constraintProfile });

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Grades"
        title="Orbit keeps grade pressure visible without turning the board into an LMS."
        description="Use the grade surface for the semester snapshot, course signals, and what-if guidance on the next weighted item."
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.45fr)_300px]">
        <div className="space-y-3">
          <Card className="surface-panel rounded-xl border hairline">
            <CardContent className="grid gap-3 p-4 md:grid-cols-2">
              <div className="rounded-xl border hairline bg-background/62 px-3.5 py-3">
                <Sigma className="size-3.5 text-primary" />
                <p className="mt-1.5 text-[12px] font-medium text-foreground">Semester GPA snapshot</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight text-foreground">{semester.gpa}</p>
                <p className="mt-1 text-[11px] text-muted-foreground">Across {semester.hours} visible credit hours.</p>
              </div>
              <div className="rounded-xl border hairline bg-background/62 px-3.5 py-3">
                <TrendingUp className="size-3.5 text-primary" />
                <p className="mt-1.5 text-[12px] font-medium text-foreground">Course cards</p>
                <p className="mt-1 text-[11px] text-muted-foreground">Orbit is watching {courseCards.length} graded courses right now.</p>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-3 xl:grid-cols-2">
            {courseCards.length ? (
              courseCards.map((card) => (
                <Card key={card.workspace.id} className="surface-card rounded-xl border hairline">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg font-semibold tracking-tight">{card.workspace.name}</CardTitle>
                    <p className="text-[12px] leading-5 text-foreground/72">{card.detail}</p>
                  </CardHeader>
                  <CardContent className="space-y-2.5">
                    <div className="rounded-lg border hairline bg-[var(--surface-soft)] px-3 py-2.5">
                      <p className="text-[12px] font-medium text-foreground">{card.title}</p>
                      <p className="mt-1 text-[11px] text-foreground/72">Target: <span className="font-mono">{card.targetValue}%</span></p>
                    </div>
                    <Link href={`/workspaces/${card.workspace.id}`} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-fit")}>
                      Open course
                    </Link>
                  </CardContent>
                </Card>
              ))
            ) : (
              <EmptyState title="No course gradebooks yet" description="Course workspaces will surface here once grade data is attached." />
            )}
          </div>

          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">What-if panel</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 xl:grid-cols-2">
              {whatIfCards.map((card) => (
                <div key={card.workspace.id} className="rounded-lg border hairline bg-[var(--surface-soft)] px-3 py-2.5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[12px] font-medium text-foreground">{card.workspace.shortLabel}</p>
                      <p className="mt-1 text-[11px] text-muted-foreground">{card.nextItemTitle ?? "No planned grade item"}</p>
                    </div>
                    <Target className="size-3.5 text-primary" />
                  </div>
                  <p className="mt-2.5 text-[11px] leading-5 text-muted-foreground">
                    {card.neededScore != null
                      ? `Orbit estimates you need about ${card.neededScore}% on the next ${card.categoryLabel?.toLowerCase() ?? "weighted"} item to stay on target.`
                      : "There is no pending grade item to model right now."}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-3">
          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Assistant output</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5 text-[12px] text-muted-foreground">
              <p>Orbit treats grades as decision input, not a standalone system.</p>
              <Link href="/assistant?intent=explain_priority" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-full justify-start")}>
                Explain priority from grade pressure
              </Link>
            </CardContent>
          </Card>
          <BuddyPanel insight={buddyInsight} plan={plan} />
        </aside>
      </div>
    </div>
  );
}

