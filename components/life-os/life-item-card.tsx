"use client";

import {
  CheckCheck,
  Circle,
  Clock3,
  MapPin,
  Sparkles,
  Wallet,
} from "lucide-react";

import { ItemPillBadges } from "@/components/life-os/item-pill-badges";
import { LifeItemDialog } from "@/components/life-os/life-item-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  formatAmount,
  formatDeadlineDistance,
  formatEstimatedMinutes,
  formatItemDateTime,
} from "@/lib/life-os/formatters";
import type { TaskView } from "@/lib/life-os/types";
import { cn } from "@/lib/utils";

function buildMeta(item: TaskView) {
  const meta = [
    formatDeadlineDistance(item.dueAt ?? item.scheduledAt),
    formatEstimatedMinutes(item),
  ];

  if (item.location) {
    meta.push(item.location);
  }

  if (item.amount != null) {
    meta.push(formatAmount(item.amount) ?? "");
  }

  return meta.filter(Boolean);
}

export function LifeItemCard({
  item,
  compact = false,
  onCompleteTask,
  onMoveTaskToTomorrow,
  onStartTask,
  onToggleFocus,
  isFocused,
}: {
  item: TaskView;
  compact?: boolean;
  onCompleteTask: () => void;
  onMoveTaskToTomorrow: () => void;
  onStartTask: () => void;
  onToggleFocus: () => void;
  isFocused: boolean;
}) {
  const isComplete = item.status === "done" || item.status === "paid";
  const meta = buildMeta(item);

  return (
    <Card
      className={cn(
        "rounded-xl border hairline bg-card/90 transition-transform duration-150 hover:-translate-y-0.5",
        compact ? "shadow-none" : "surface-card",
        isFocused && "ring-2 ring-primary/20",
      )}
    >
      <CardContent className={cn("space-y-3.5", compact ? "p-3.5" : "p-4")}>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2.5">
            <div className="space-y-1.5">
              <p
                className={cn(
                  "text-[15px] font-semibold tracking-tight text-foreground",
                  compact && "text-[14px]",
                  isComplete && "text-muted-foreground line-through",
                )}
              >
                {item.title}
              </p>
              <ItemPillBadges item={item} />
            </div>

            {item.notes ? (
              <p className="max-w-2xl text-[13px] leading-5 text-muted-foreground">
                {item.notes}
              </p>
            ) : null}

            <div className="flex flex-wrap items-center gap-3 text-[12px] text-muted-foreground">
              <span className="inline-flex items-center gap-1.5 font-mono">
                <Clock3 className="size-3.5" />
                {formatItemDateTime(item.scheduledAt ?? item.dueAt)}
              </span>
              {item.location ? (
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="size-3.5" />
                  {item.location}
                </span>
              ) : null}
              {item.amount != null ? (
                <span className="inline-flex items-center gap-1.5 font-mono">
                  <Wallet className="size-3.5" />
                  {formatAmount(item.amount)}
                </span>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-1.5">
              {meta.map((entry) => (
                <span
                  key={`${item.id}-${entry}`}
                  className="rounded-md border hairline bg-[var(--surface-soft)] px-2 py-0.5 font-mono text-[11px] text-muted-foreground"
                >
                  {entry}
                </span>
              ))}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2 self-start">
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant={isFocused ? "default" : "outline"}
                    size="icon-sm"
                    aria-label={isFocused ? "Remove focus today" : "Mark focus today"}
                  />
                }
                onClick={onToggleFocus}
              >
                <Sparkles className="size-4" />
              </TooltipTrigger>
              <TooltipContent>
                {isFocused ? "Remove focus today" : "Mark focus today"}
              </TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant={isComplete ? "secondary" : "outline"}
                    size="icon-sm"
                    disabled={isComplete}
                    aria-label={item.kind === "bill" ? "Mark paid" : "Mark completed"}
                  />
                }
                onClick={onCompleteTask}
              >
                {isComplete ? <CheckCheck className="size-4" /> : <Circle className="size-4" />}
              </TooltipTrigger>
              <TooltipContent>
                {isComplete
                  ? "Already completed"
                  : item.kind === "bill"
                    ? "Mark paid"
                    : "Mark complete"}
              </TooltipContent>
            </Tooltip>

            <LifeItemDialog
              item={item}
              onCompleteTask={onCompleteTask}
              onMoveTaskToTomorrow={onMoveTaskToTomorrow}
              onStartTask={onStartTask}
              onToggleFocus={onToggleFocus}
              isFocused={isFocused}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
