import { ArrowRight, CalendarPlus2, CheckCheck, Play, Sparkles } from "lucide-react";

import { ItemPillBadges } from "@/components/life-os/item-pill-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatEstimatedMinutes } from "@/lib/life-os/formatters";
import type { TodayRecommendationResult } from "@/lib/life-os/types";

function getConfidenceLabel(score: number) {
  if (score >= 95) {
    return "High confidence";
  }

  if (score >= 70) {
    return "Strong fit";
  }

  return "Useful next move";
}

export function RecommendationCard({
  recommendations,
  onCompleteTask,
  onMoveTaskToTomorrow,
  onStartTask,
}: {
  recommendations: TodayRecommendationResult;
  onCompleteTask: (taskId: string) => void;
  onMoveTaskToTomorrow: (taskId: string) => void;
  onStartTask: (taskId: string) => void;
}) {
  if (!recommendations.primary) {
    return (
      <Card className="surface-glass rounded-2xl">
        <CardContent className="p-6">
          <p className="text-2xl font-semibold tracking-tight text-foreground">
            A calm open day.
          </p>
          <p className="mt-2 max-w-md text-[13px] leading-5 text-muted-foreground">
            Nothing urgent is pressing right now. Protect one meaningful block and let the rest of
            the day stay light.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { primary, secondary } = recommendations;
  const confidenceLabel = getConfidenceLabel(primary.score);

  return (
    <Card className="surface-glass overflow-hidden rounded-2xl ring-1 ring-primary/10">
      <CardHeader className="space-y-4 border-b hairline pb-5">
        <div className="flex items-center justify-between gap-3">
          <div className="inline-flex w-fit items-center gap-1.5 rounded-md bg-primary/10 px-2.5 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-primary">
            <Sparkles className="size-3.5" />
            What should I do today?
          </div>
          <span className="rounded-md bg-[var(--surface-soft)] px-2.5 py-1 font-mono text-[11px] font-medium text-muted-foreground">
            <span className="text-foreground">{primary.score}</span> · {confidenceLabel}
          </span>
        </div>
        <div
          key={primary.item.id}
          className="space-y-3 animate-in fade-in-0 slide-in-from-right-3 duration-300"
        >
          <CardTitle className="text-2xl font-semibold tracking-tight text-foreground">
            {primary.item.title}
          </CardTitle>
          <p className="max-w-xl text-[13px] leading-5 text-foreground/80">{primary.reason}</p>
          <p className="text-[13px] leading-5 text-muted-foreground">{primary.explanation}</p>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 p-6">
        <div
          key={`${primary.item.id}-details`}
          className="space-y-5 animate-in fade-in-0 slide-in-from-left-3 duration-300"
        >
          <ItemPillBadges item={primary.item} />

          <div className="rounded-xl border hairline bg-[var(--surface-soft)] p-4">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Recommendation signals
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {primary.scoreBreakdown.map((signal) => (
                <span
                  key={signal}
                  className="rounded-md border hairline bg-card px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
                >
                  {signal}
                </span>
              ))}
            </div>
            <p className="mt-3 text-[13px] text-muted-foreground">
              Estimated lift:{" "}
              <span className="font-mono font-medium text-foreground">
                {formatEstimatedMinutes(primary.item)}
              </span>
            </p>
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            <Button onClick={() => onStartTask(primary.item.id)}>
              <Play className="size-4" />
              Start now
            </Button>
            <Button variant="outline" onClick={() => onMoveTaskToTomorrow(primary.item.id)}>
              <CalendarPlus2 className="size-4" />
              Move to tomorrow
            </Button>
            <Button variant="outline" onClick={() => onCompleteTask(primary.item.id)}>
              <CheckCheck className="size-4" />
              Mark done
            </Button>
          </div>
        </div>

        {secondary.length ? (
          <div className="space-y-3">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Then keep momentum with
            </p>
            <div className="space-y-2">
              {secondary.map((entry) => (
                <div
                  key={entry.item.id}
                  className="flex items-center justify-between gap-3 rounded-lg border hairline bg-card/80 px-3.5 py-2.5"
                >
                  <div>
                    <p className="text-[13px] font-medium text-foreground">{entry.item.title}</p>
                    <p className="text-[12px] text-muted-foreground">{entry.explanation}</p>
                  </div>
                  <ArrowRight className="size-4 text-muted-foreground" />
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
