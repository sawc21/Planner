"use client";

import Link from "next/link";
import {
  HandCoins,
  Layers3,
  ShieldCheck,
  Sparkles,
  TimerReset,
} from "lucide-react";

import { LifeItemCard } from "@/components/life-os/life-item-card";
import { OverloadWarningCard } from "@/components/life-os/overload-warning-card";
import { PageHeader } from "@/components/life-os/page-header";
import { RecommendationCard } from "@/components/life-os/recommendation-card";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  buildDailyNarrative,
  getOverdueItems,
  getOverloadAssessment,
  getTodayRecommendations,
  getUpcomingDeadlines,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import type { LifeItem } from "@/lib/life-os/types";
import { cn } from "@/lib/utils";

export function CommandCenterView() {
  const { items, focusTodayIds, toggleFocusToday, toggleItemCompletion } = useLifeOs();
  const recommendations = getTodayRecommendations(items);
  const overload = getOverloadAssessment(items);
  const narrative = buildDailyNarrative(items);
  const overdueItems = getOverdueItems(items).slice(0, 2);
  const upcomingItems = getUpcomingDeadlines(items).slice(0, 2);
  const rankedItems = [
    recommendations.primary?.item,
    ...recommendations.secondary.map((entry) => entry.item),
  ].filter((item): item is LifeItem => Boolean(item));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Command Center"
        title="Plan the day without turning it into a crisis."
        description="A daily cockpit for choosing the next move, balancing load, and keeping the rest of the board in perspective."
      />

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <RecommendationCard recommendations={recommendations} />
        <OverloadWarningCard assessment={overload} />
      </div>

      <section className="grid gap-4 xl:grid-cols-[0.88fr_1.12fr]">
        <Card className="surface-card border hairline">
          <CardHeader>
            <CardTitle className="font-heading text-2xl">Narrative summary</CardTitle>
            <p className="text-sm leading-6 text-muted-foreground">
              A concise read on what today is asking for, based on the seeded planning logic.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="rounded-[24px] bg-[var(--surface-soft)] p-4 text-sm leading-7 text-foreground">
              {narrative}
            </p>
            <div className="grid gap-3 sm:grid-cols-3">
              <Link
                href="/deadlines?bucket=overdue"
                className="rounded-[24px] bg-[var(--surface-soft)] p-4 transition-transform hover:-translate-y-0.5"
              >
                <HandCoins className="size-5 text-primary" />
                <p className="mt-3 font-medium text-foreground">Clear one overdue item</p>
                <p className="mt-1 text-sm text-muted-foreground">Buy the day a little relief.</p>
              </Link>
              <Link
                href="/tasks?scope=today"
                className="rounded-[24px] bg-[var(--surface-soft)] p-4 transition-transform hover:-translate-y-0.5"
              >
                <Sparkles className="size-5 text-primary" />
                <p className="mt-3 font-medium text-foreground">Protect a focus pick</p>
                <p className="mt-1 text-sm text-muted-foreground">Choose one task to shield.</p>
              </Link>
              <Link
                href="/calendar"
                className="rounded-[24px] bg-[var(--surface-soft)] p-4 transition-transform hover:-translate-y-0.5"
              >
                <TimerReset className="size-5 text-primary" />
                <p className="mt-3 font-medium text-foreground">Rebalance the week</p>
                <p className="mt-1 text-sm text-muted-foreground">Look for something to move.</p>
              </Link>
            </div>
          </CardContent>
        </Card>

        <Card className="surface-card border hairline">
          <CardHeader>
            <CardTitle className="font-heading text-2xl">Priority board</CardTitle>
            <p className="text-sm leading-6 text-muted-foreground">
              The short list underneath today&apos;s recommendation.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {rankedItems.map((item) => (
              <LifeItemCard
                key={item.id}
                compact
                item={item}
                onToggleComplete={() => toggleItemCompletion(item.id)}
                onToggleFocus={() => toggleFocusToday(item.id)}
                isFocused={focusTodayIds.includes(item.id)}
              />
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="surface-card border hairline">
          <CardHeader>
            <CardTitle className="font-heading text-2xl">Quick action tiles</CardTitle>
            <p className="text-sm leading-6 text-muted-foreground">
              Simple, calming actions when you need momentum more than complexity.
            </p>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-[24px] bg-[var(--surface-soft)] p-4">
              <ShieldCheck className="size-5 text-primary" />
              <p className="mt-3 font-medium text-foreground">Choose one anchor</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Keep the rest of the board secondary until the anchor moves.
              </p>
            </div>
            <div className="rounded-[24px] bg-[var(--surface-soft)] p-4">
              <HandCoins className="size-5 text-primary" />
              <p className="mt-3 font-medium text-foreground">Pay the fastest bill</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Clearing one financial loose end creates instant quiet.
              </p>
            </div>
            <div className="rounded-[24px] bg-[var(--surface-soft)] p-4">
              <Layers3 className="size-5 text-primary" />
              <p className="mt-3 font-medium text-foreground">Drop one medium item</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Move a nonessential task before it starts wearing down the day.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="surface-card border hairline">
          <CardHeader>
            <CardTitle className="font-heading text-2xl">Pressure points</CardTitle>
            <p className="text-sm leading-6 text-muted-foreground">
              The items most likely to create drag if they stay unattended.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {[...overdueItems, ...upcomingItems].map((item) => (
              <LifeItemCard
                key={item.id}
                compact
                item={item}
                onToggleComplete={() => toggleItemCompletion(item.id)}
                onToggleFocus={() => toggleFocusToday(item.id)}
                isFocused={focusTodayIds.includes(item.id)}
              />
            ))}
            <Link
              href="/tasks?scope=overdue"
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-fit")}
            >
              Open the filtered task list
            </Link>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
