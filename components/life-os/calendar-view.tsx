"use client";

import { CalendarX2, Clock3 } from "lucide-react";

import { EmptyState } from "@/components/life-os/empty-state";
import { LifeItemCard } from "@/components/life-os/life-item-card";
import { PageHeader } from "@/components/life-os/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatItemDay } from "@/lib/life-os/formatters";
import { groupItemsByAgendaDay } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";

export function CalendarView() {
  const { items, focusTodayIds, toggleFocusToday, toggleItemCompletion } = useLifeOs();
  const agendaGroups = groupItemsByAgendaDay(items);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Calendar"
        title="Agenda-style, on purpose."
        description="Just today plus the next seven days, grouped in a way that keeps the schedule legible and the MVP focused."
      />

      <div className="grid gap-4 xl:grid-cols-2">
        {agendaGroups.map((group) => (
          <Card key={group.key} className="surface-card border hairline">
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <div>
                <CardTitle className="font-heading text-2xl">{group.label}</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">
                  {formatItemDay(group.date.toISOString())}
                </p>
              </div>
              <span className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs text-muted-foreground">
                {group.items.length} scheduled
              </span>
            </CardHeader>
            <CardContent>
              {group.items.length ? (
                <ScrollArea className="max-h-[420px] pr-3">
                  <div className="space-y-3">
                    {group.items.map((item) => (
                      <LifeItemCard
                        key={item.id}
                        compact
                        item={item}
                        onToggleComplete={() => toggleItemCompletion(item.id)}
                        onToggleFocus={() => toggleFocusToday(item.id)}
                        isFocused={focusTodayIds.includes(item.id)}
                      />
                    ))}
                  </div>
                </ScrollArea>
              ) : (
                <EmptyState
                  icon={group.isToday ? Clock3 : CalendarX2}
                  title={group.isToday ? "A little white space today" : "Nothing scheduled here"}
                  description={
                    group.isToday
                      ? "No appointments or scheduled reminders are sitting on today's agenda."
                      : "This day is still open, which makes it a good candidate for rescheduling if the week gets noisy."
                  }
                />
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
