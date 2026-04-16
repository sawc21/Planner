"use client";

import { MapPin, Play, Sparkles, Wallet } from "lucide-react";

import { ItemPillBadges } from "@/components/life-os/item-pill-badges";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import {
  formatAmount,
  formatEstimatedMinutes,
  formatItemDateTime,
} from "@/lib/life-os/formatters";
import type { TaskView } from "@/lib/life-os/types";

export function LifeItemDialog({
  item,
  onCompleteTask,
  onMoveTaskToTomorrow,
  onStartTask,
  onToggleFocus,
  isFocused,
}: {
  item: TaskView;
  onCompleteTask: () => void;
  onMoveTaskToTomorrow: () => void;
  onStartTask: () => void;
  onToggleFocus: () => void;
  isFocused: boolean;
}) {
  const isComplete = item.status === "done" || item.status === "paid";

  return (
    <Dialog>
      <DialogTrigger
        render={
          <Button variant="ghost" size="sm" className="text-muted-foreground" />
        }
      >
        Details
      </DialogTrigger>
      <DialogContent className="max-w-lg gap-5">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl">{item.title}</DialogTitle>
          <DialogDescription>
            {item.notes ?? "A grounded next step with enough context to move cleanly."}
          </DialogDescription>
        </DialogHeader>

        <ItemPillBadges item={item} />

        <div className="grid gap-4 rounded-2xl bg-[var(--surface-soft)] p-4 sm:grid-cols-2">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Workspace
            </p>
            <p className="text-sm text-foreground">
              {item.workspace.name} · {item.workspace.ownerLabel}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Timing
            </p>
            <p className="text-sm text-foreground">
              {formatItemDateTime(item.scheduledAt ?? item.dueAt)}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Energy + effort
            </p>
            <p className="text-sm text-foreground">
              {item.energy} energy · {formatEstimatedMinutes(item)}
            </p>
          </div>
          {item.location ? (
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Location
              </p>
              <p className="flex items-center gap-2 text-sm text-foreground">
                <MapPin className="size-3.5 text-muted-foreground" />
                {item.location}
              </p>
            </div>
          ) : null}
          {item.amount != null ? (
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Amount
              </p>
              <p className="flex items-center gap-2 text-sm text-foreground">
                <Wallet className="size-3.5 text-muted-foreground" />
                {formatAmount(item.amount)}
              </p>
            </div>
          ) : null}
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Tags
          </p>
          <div className="flex flex-wrap gap-2">
            {item.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs text-muted-foreground"
              >
                #{tag}
              </span>
            ))}
          </div>
        </div>

        <Separator />

        <DialogFooter>
          <Button variant="outline" onClick={onStartTask} disabled={isComplete}>
            <Play className="size-4" />
            Start now
          </Button>
          <Button variant="outline" onClick={onMoveTaskToTomorrow}>
            Move to tomorrow
          </Button>
          <Button variant="outline" onClick={onToggleFocus}>
            <Sparkles className="size-4" />
            {isFocused ? "Remove focus" : "Mark focus"}
          </Button>
          <Button onClick={onCompleteTask} disabled={isComplete}>
            {item.kind === "bill" ? "Mark paid" : "Mark done"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
