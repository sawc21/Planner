import { ArrowRight, Sparkles } from "lucide-react";

import { ItemPillBadges } from "@/components/life-os/item-pill-badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatEstimatedMinutes } from "@/lib/life-os/formatters";
import type { TodayRecommendationResult } from "@/lib/life-os/types";

export function RecommendationCard({
  recommendations,
}: {
  recommendations: TodayRecommendationResult;
}) {
  if (!recommendations.primary) {
    return (
      <Card className="surface-card border hairline">
        <CardContent className="p-6">
          <p className="font-heading text-2xl text-foreground">A calm open day.</p>
          <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
            Nothing urgent is pressing right now. Protect one meaningful block and let the rest of
            the day stay light.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { primary, secondary } = recommendations;

  return (
    <Card className="surface-card border hairline">
      <CardHeader className="space-y-3">
        <div className="inline-flex w-fit items-center gap-2 rounded-full bg-[var(--attention-soft)] px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-foreground">
          <Sparkles className="size-3.5" />
          What should I do today?
        </div>
        <CardTitle className="font-heading text-3xl tracking-tight">
          {primary.item.title}
        </CardTitle>
        <p className="max-w-xl text-sm leading-6 text-muted-foreground">{primary.reason}</p>
      </CardHeader>
      <CardContent className="space-y-5">
        <ItemPillBadges item={primary.item} />
        <div className="rounded-2xl bg-[var(--surface-soft)] p-4 text-sm text-muted-foreground">
          Estimated lift: <span className="font-medium text-foreground">{formatEstimatedMinutes(primary.item)}</span>
        </div>
        {secondary.length ? (
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Then keep momentum with
            </p>
            <div className="space-y-3">
              {secondary.map((entry) => (
                <div
                  key={entry.item.id}
                  className="flex items-center justify-between gap-3 rounded-2xl border hairline bg-card/80 px-4 py-3"
                >
                  <div>
                    <p className="font-medium text-foreground">{entry.item.title}</p>
                    <p className="text-sm text-muted-foreground">{entry.reason}</p>
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
