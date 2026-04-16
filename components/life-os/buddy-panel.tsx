import Link from "next/link";
import { Brain, Sparkles } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { StudyBuddyInsight, StudyPlan } from "@/lib/life-os/types";
import { cn } from "@/lib/utils";

export function BuddyPanel({
  insight,
  plan,
}: {
  insight: StudyBuddyInsight;
  plan?: StudyPlan;
}) {
  return (
    <Card className="surface-card border hairline">
      <CardHeader className="space-y-3">
        <div className="inline-flex w-fit items-center gap-2 rounded-full bg-[var(--attention-soft)] px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-foreground">
          <Brain className="size-3.5" />
          {insight.title}
        </div>
        <CardTitle className="font-heading text-2xl">Context-aware planning</CardTitle>
        <p className="text-sm leading-6 text-foreground/72">{insight.summary}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          {insight.bullets.map((bullet) => (
            <div key={bullet} className="rounded-2xl bg-[var(--surface-soft)] px-4 py-3 text-sm text-foreground/82">
              {bullet}
            </div>
          ))}
        </div>
        {plan ? (
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Suggested flow
            </p>
            {plan.steps.map((step) => (
              <div key={step.id} className="rounded-2xl border hairline bg-white/80 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-foreground">{step.title}</p>
                    <p className="mt-1 text-sm text-foreground/72">{step.reason}</p>
                  </div>
                  <span className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs text-muted-foreground">
                    {step.minutes} min
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : null}
        <Link href={insight.actionHref} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-fit")}>
          <Sparkles className="size-4" />
          {insight.actionLabel}
        </Link>
      </CardContent>
    </Card>
  );
}
