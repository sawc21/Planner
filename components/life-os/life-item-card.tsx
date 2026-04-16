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
        "border hairline bg-card/90 transition-transform duration-150 hover:-translate-y-0.5",
        compact ? "shadow-none" : "surface-card",
        isFocused && "ring-2 ring-primary/20",
      )}
    >
      <CardContent className={cn("space-y-4", compact ? "p-4" : "p-5")}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <div className="space-y-2">
              <p
                className={cn(
                  "text-lg font-semibold tracking-tight text-foreground/95",
                  compact && "text-base",
                  isComplete && "text-muted-foreground line-through",
                )}
              >
                {item.title}
              </p>
              <ItemPillBadges item={item} />
            </div>

            {item.notes ? (
              <p className="max-w-2xl text-sm leading-6 text-foreground/72">
                {item.notes}
              </p>
            ) : null}

            <div className="flex flex-wrap items-center gap-3 text-sm text-foreground/72">
              <span className="inline-flex items-center gap-1.5">
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
                <span className="inline-flex items-center gap-1.5">
                  <Wallet className="size-3.5" />
                  {formatAmount(item.amount)}
                </span>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-2">
              {meta.map((entry) => (
                <span
                  key={`${item.id}-${entry}`}
                  className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs text-muted-foreground"
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
