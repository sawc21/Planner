import { Clock3, MapPin } from "lucide-react";

import { WorkspaceIcon } from "@/components/life-os/workspace-icon";
import { Card, CardContent } from "@/components/ui/card";
import { formatItemDateTime } from "@/lib/life-os/formatters";
import type { EventView } from "@/lib/life-os/types";

export function EventCard({
  event,
  compact = false,
}: {
  event: EventView;
  compact?: boolean;
}) {
  return (
    <Card className="border hairline bg-card/90 shadow-none">
      <CardContent className={compact ? "p-4" : "p-5"}>
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${event.workspace.colorToken}`}
              >
                <WorkspaceIcon icon={event.workspace.icon} className="size-3.5" />
                {event.workspace.shortLabel}
              </span>
              <span className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs text-muted-foreground">
                {event.kind.replace("_", " ")}
              </span>
            </div>
            <p className={`font-semibold tracking-tight text-foreground/95 ${compact ? "text-base" : "text-lg"}`}>
              {event.title}
            </p>
            {event.notes ? (
              <p className="max-w-2xl text-sm leading-6 text-foreground/72">{event.notes}</p>
            ) : null}
            <div className="flex flex-wrap gap-3 text-sm text-foreground/72">
              <span className="inline-flex items-center gap-1.5">
                <Clock3 className="size-3.5" />
                {formatItemDateTime(event.startAt)}
              </span>
              {event.location ? (
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="size-3.5" />
                  {event.location}
                </span>
              ) : null}
            </div>
          </div>
          <span className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs text-muted-foreground">
            {event.workspace.name}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
