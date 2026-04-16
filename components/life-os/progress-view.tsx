"use client";

import { Target, TrendingUp } from "lucide-react";

import { EmptyState } from "@/components/life-os/empty-state";
import { PageHeader } from "@/components/life-os/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getProgressCards } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";

export function ProgressView() {
  const { workspaces, tasks, gradebooks, progressRecords } = useLifeOs();
  const { courseCards, trackCards, lifeCards } = getProgressCards({
    workspaces,
    tasks,
    gradebooks,
    progressRecords,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Progress"
        title="Track what is actually moving."
        description="Courses get grade logic, study tracks get milestone progress, and life/work contexts get lighter progress summaries without pretending everything is a grade."
      />

      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight text-foreground">Course grade board</h2>
        <div className="grid gap-4 xl:grid-cols-2">
          {courseCards.length ? (
            courseCards.map((card) => (
              <Card key={card.workspace.id} className="surface-card rounded-xl border hairline">
                <CardHeader>
                  <CardTitle className="text-xl font-semibold tracking-tight">{card.workspace.name}</CardTitle>
                  <p className="text-[13px] leading-5 text-foreground/72">{card.detail}</p>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
                    <p className="text-[13px] font-medium text-foreground">{card.title}</p>
                    <p className="mt-1 text-[12px] text-foreground/72">
                      Target: <span className="font-mono">{card.targetValue}%</span>
                    </p>
                  </div>
                  {card.neededOnNext != null ? (
                    <div className="rounded-lg border hairline bg-[var(--attention-soft)] p-3.5">
                      <Target className="size-4 text-foreground" />
                      <p className="mt-2 text-[12px] text-foreground/82">
                        What-if view: hitting roughly <span className="font-mono">{card.neededOnNext}%</span> on the next weighted item keeps this course on track.
                      </p>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            ))
          ) : (
            <EmptyState
              title="No course gradebooks yet"
              description="Course workspaces will surface here once grade data is attached."
            />
          )}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight text-foreground">Study track momentum</h2>
        <div className="grid gap-4 xl:grid-cols-2">
          {trackCards.length ? (
            trackCards.map((card) => (
              <Card key={card.workspace.id} className="surface-card rounded-xl border hairline">
                <CardHeader>
                  <CardTitle className="text-xl font-semibold tracking-tight">{card.workspace.name}</CardTitle>
                  <p className="text-[13px] leading-5 text-foreground/72">{card.detail}</p>
                </CardHeader>
                <CardContent>
                  <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
                    <p className="text-[13px] font-medium text-foreground">{card.title}</p>
                    <div className="mt-3 h-1.5 rounded-full bg-border/70">
                      <div
                        className="h-1.5 rounded-full bg-primary"
                        style={{
                          width: `${Math.min(100, (card.currentValue / Math.max(card.targetValue ?? 1, 1)) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          ) : (
            <EmptyState
              title="No study tracks yet"
              description="Study-track progress will appear here when structured learning flows are present."
            />
          )}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight text-foreground">Life and work progress</h2>
        <div className="grid gap-4 xl:grid-cols-3">
          {lifeCards.map((card) => (
            <Card key={card.workspace.id} className="surface-card rounded-xl border hairline">
              <CardHeader>
                <CardTitle className="text-xl font-semibold tracking-tight">{card.workspace.name}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
                  <TrendingUp className="size-4 text-primary" />
                  <p className="mt-2 text-[13px] font-medium text-foreground">{card.title}</p>
                  <p className="mt-1 text-[12px] text-foreground/72">{card.detail}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
