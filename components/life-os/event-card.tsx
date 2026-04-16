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
    <Card className="rounded-xl border hairline bg-card/90 shadow-none">
      <CardContent className={compact ? "p-3.5" : "p-4"}>
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <span
                className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 font-mono text-[11px] font-medium ${event.workspace.colorToken}`}
              >
                <WorkspaceIcon icon={event.workspace.icon} className="size-3.5" />
                {event.workspace.shortLabel}
              </span>
              <span className="rounded-md border hairline bg-[var(--surface-soft)] px-2 py-0.5 text-[11px] text-muted-foreground">
                {event.kind.replace("_", " ")}
              </span>
            </div>
            <p
              className={`font-semibold tracking-tight text-foreground ${compact ? "text-[14px]" : "text-[15px]"}`}
            >
              {event.title}
            </p>
            {event.notes ? (
              <p className="max-w-2xl text-[13px] leading-5 text-muted-foreground">
                {event.notes}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-3 text-[12px] text-muted-foreground">
              <span className="inline-flex items-center gap-1.5 font-mono">
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
          <span className="rounded-md bg-[var(--surface-soft)] px-2 py-0.5 text-[11px] text-muted-foreground">
            {event.workspace.name}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
