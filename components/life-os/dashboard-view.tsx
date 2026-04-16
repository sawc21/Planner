"use client";

import Link from "next/link";
import { format } from "date-fns";
import {
  AlertCircle,
  CalendarClock,
  Flame,
  Layers3,
  ListChecks,
  Sparkles,
} from "lucide-react";

import { EmptyState } from "@/components/life-os/empty-state";
import { LifeItemCard } from "@/components/life-os/life-item-card";
import { MetricCard } from "@/components/life-os/metric-card";
import { OverloadWarningCard } from "@/components/life-os/overload-warning-card";
import { PageHeader } from "@/components/life-os/page-header";
import { RecommendationCard } from "@/components/life-os/recommendation-card";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getOverdueItems,
  getOverloadAssessment,
  getTodayItems,
  getTodayRecommendations,
  getTopPriorityItems,
  getUpcomingDeadlines,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

function WidgetFrame({
  title,
  description,
  href,
  children,
}: {
  title: string;
  description: string;
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="surface-card border hairline">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="font-heading text-2xl">{title}</CardTitle>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        <Link href={href} className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
          Open
        </Link>
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}

export function DashboardView() {
  const { items, focusTodayIds, toggleFocusToday, toggleItemCompletion } = useLifeOs();
  const todayItems = getTodayItems(items);
  const overdueItems = getOverdueItems(items);
  const topPriorityItems = getTopPriorityItems(items, 4);
  const upcomingDeadlines = getUpcomingDeadlines(items);
  const recommendations = getTodayRecommendations(items);
  const overload = getOverloadAssessment(items);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Dashboard"
        title="A steadier shape for the day."
        description="See the whole board at a glance, then move toward the one action that makes the rest of the list easier to hold."
      />

      <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="surface-panel overflow-hidden border-none">
          <CardContent className="space-y-6 p-6">
            <div className="space-y-3">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">
                {format(new Date(), "EEEE, MMMM d")}
              </p>
              <h2 className="font-heading text-4xl tracking-tight text-foreground">
                What needs your calm attention first?
              </h2>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                Today blends time-sensitive admin, real appointments, and a few errands that can be
                cleared without drama. Use the recommendation card to pick your opening move.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <MetricCard
                label="Today"
                value={String(todayItems.length)}
                detail="Items touching today's calendar"
                icon={Layers3}
              />
              <MetricCard
                label="Overdue"
                value={String(overdueItems.length)}
                detail="Loose ends asking for closure"
                icon={AlertCircle}
              />
              <MetricCard
                label="Focus"
                value={String(focusTodayIds.length)}
                detail="Items you've marked to protect"
                icon={Sparkles}
              />
            </div>
          </CardContent>
        </Card>

        <RecommendationCard recommendations={recommendations} />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <WidgetFrame
          title="Top priorities"
          description="The highest-stakes items, ranked so you can see pressure before it gets noisy."
          href="/tasks?priority=high"
        >
          {topPriorityItems.map((item) => (
            <LifeItemCard
              key={item.id}
              compact
              item={item}
              onToggleComplete={() => toggleItemCompletion(item.id)}
              onToggleFocus={() => toggleFocusToday(item.id)}
              isFocused={focusTodayIds.includes(item.id)}
            />
          ))}
        </WidgetFrame>

        <WidgetFrame
          title="Overdue items"
          description="The oldest friction points still hanging over the board."
          href="/deadlines?bucket=overdue"
        >
          {overdueItems.length ? (
            overdueItems.slice(0, 3).map((item) => (
              <LifeItemCard
                key={item.id}
                compact
                item={item}
                onToggleComplete={() => toggleItemCompletion(item.id)}
                onToggleFocus={() => toggleFocusToday(item.id)}
                isFocused={focusTodayIds.includes(item.id)}
              />
            ))
          ) : (
            <EmptyState
              icon={Flame}
              title="No overdue drift"
              description="Nothing has tipped into the red. Keep the margin and let it stay that way."
            />
          )}
        </WidgetFrame>

        <WidgetFrame
          title="Today's plan"
          description="Everything currently pulling on today's attention, from appointments to admin."
          href="/tasks?scope=today"
        >
          {todayItems.slice(0, 4).map((item) => (
            <LifeItemCard
              key={item.id}
              compact
              item={item}
              onToggleComplete={() => toggleItemCompletion(item.id)}
              onToggleFocus={() => toggleFocusToday(item.id)}
              isFocused={focusTodayIds.includes(item.id)}
            />
          ))}
        </WidgetFrame>

        <WidgetFrame
          title="Upcoming deadlines"
          description="What comes into play next so later-this-week work never arrives as a surprise."
          href="/deadlines?bucket=next3Days"
        >
          {upcomingDeadlines.map((item) => (
            <LifeItemCard
              key={item.id}
              compact
              item={item}
              onToggleComplete={() => toggleItemCompletion(item.id)}
              onToggleFocus={() => toggleFocusToday(item.id)}
              isFocused={focusTodayIds.includes(item.id)}
            />
          ))}
        </WidgetFrame>
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.78fr_1.22fr]">
        <OverloadWarningCard assessment={overload} />

        <Card className="surface-card border hairline">
          <CardHeader>
            <CardTitle className="font-heading text-2xl">Quick links</CardTitle>
            <p className="text-sm leading-6 text-muted-foreground">
              Jump straight into the view that matches the kind of work you want to sort.
            </p>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-3">
            <Link
              href="/tasks?status=todo"
              className="rounded-[24px] bg-[var(--surface-soft)] p-4 transition-transform hover:-translate-y-0.5"
            >
              <ListChecks className="size-5 text-primary" />
              <p className="mt-3 font-medium text-foreground">Clear the general list</p>
              <p className="mt-1 text-sm text-muted-foreground">Filter to open tasks and bills.</p>
            </Link>
            <Link
              href="/calendar"
              className="rounded-[24px] bg-[var(--surface-soft)] p-4 transition-transform hover:-translate-y-0.5"
            >
              <CalendarClock className="size-5 text-primary" />
              <p className="mt-3 font-medium text-foreground">See the next 7 days</p>
              <p className="mt-1 text-sm text-muted-foreground">Agenda view for everything scheduled.</p>
            </Link>
            <Link
              href="/command-center"
              className="rounded-[24px] bg-[var(--surface-soft)] p-4 transition-transform hover:-translate-y-0.5"
            >
              <Sparkles className="size-5 text-primary" />
              <p className="mt-3 font-medium text-foreground">Plan the day</p>
              <p className="mt-1 text-sm text-muted-foreground">See the narrative and rebalance gently.</p>
            </Link>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
