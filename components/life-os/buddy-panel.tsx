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
    <Card className="surface-card rounded-xl border hairline">
      <CardHeader className="space-y-3">
        <div className="inline-flex w-fit items-center gap-2 rounded-md bg-[var(--attention-soft)] px-2.5 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-foreground">
          <Brain className="size-3.5" />
          {insight.title}
        </div>
        <CardTitle className="text-xl font-semibold tracking-tight">Context-aware planning</CardTitle>
        <p className="text-[13px] leading-5 text-foreground/72">{insight.summary}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2.5">
          {insight.bullets.map((bullet) => (
            <div key={bullet} className="rounded-lg border hairline bg-[var(--surface-soft)] px-3.5 py-2.5 text-[13px] text-foreground/82">
              {bullet}
            </div>
          ))}
        </div>
        {plan ? (
          <div className="space-y-3">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Suggested flow
            </p>
            {plan.steps.map((step) => (
              <div key={step.id} className="rounded-lg border hairline bg-card/80 p-3.5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[13px] font-medium text-foreground">{step.title}</p>
                    <p className="mt-1 text-[12px] text-foreground/72">{step.reason}</p>
                  </div>
                  <span className="rounded-md border hairline bg-[var(--surface-soft)] px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
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
