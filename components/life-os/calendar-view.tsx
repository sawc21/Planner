"use client";

import { CalendarX2, Clock3 } from "lucide-react";

import { EmptyState } from "@/components/life-os/empty-state";
import { EventCard } from "@/components/life-os/event-card";
import { LifeItemCard } from "@/components/life-os/life-item-card";
import { PageHeader } from "@/components/life-os/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatItemDay } from "@/lib/life-os/formatters";
import { getAgendaGroups } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";

export function CalendarView() {
  const {
    workspaces,
    tasks,
    events,
    focusTodayIds,
    toggleFocusToday,
    completeTask,
    moveTaskToTomorrow,
    startTask,
  } = useLifeOs();
  const agendaGroups = getAgendaGroups({ workspaces, tasks, events });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Agenda"
        title="See the week with context."
        description="Tasks and events stay together so class time, study blocks, bills, errands, and work all compete in the same honest timeline."
      />

      <div className="grid gap-4 xl:grid-cols-2">
        {agendaGroups.map((group) => (
          <Card key={group.key} className="surface-card rounded-xl border hairline">
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <div>
                <CardTitle className="text-xl font-semibold tracking-tight">{group.label}</CardTitle>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  <span className="font-mono">{formatItemDay(group.date.toISOString())}</span> · {group.pressureLabel}
                </p>
              </div>
              <span className="rounded-md border hairline bg-[var(--surface-soft)] px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
                {group.entries.length} items
              </span>
            </CardHeader>
            <CardContent>
              {group.entries.length ? (
                <ScrollArea className="max-h-[460px] pr-3">
                  <div className="space-y-3">
                    {group.entries.map((entry) =>
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
                    )}
                  </div>
                </ScrollArea>
              ) : (
                <EmptyState
                  icon={group.isToday ? Clock3 : CalendarX2}
                  title={group.isToday ? "A little white space today" : "Nothing scheduled here"}
                  description={
                    group.isToday
                      ? "No tasks or events are currently pulling on today's schedule."
                      : "This day is still open, which makes it a good candidate for rebalancing if the week tightens."
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
