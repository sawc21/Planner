"use client";

import { MapPin, Sparkles, Wallet } from "lucide-react";

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
import { formatAmount, formatEstimatedMinutes, formatItemDateTime } from "@/lib/life-os/formatters";
import type { LifeItem } from "@/lib/life-os/types";
import { ItemPillBadges } from "@/components/life-os/item-pill-badges";

export function LifeItemDialog({
  item,
  onToggleComplete,
  onToggleFocus,
  isFocused,
}: {
  item: LifeItem;
  onToggleComplete: () => void;
  onToggleFocus: () => void;
  isFocused: boolean;
}) {
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
          <DialogDescription>{item.notes ?? "A steady next step with enough context to move."}</DialogDescription>
        </DialogHeader>

        <ItemPillBadges item={item} />

        <div className="grid gap-4 rounded-2xl bg-[var(--surface-soft)] p-4 sm:grid-cols-2">
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
          <Button variant="outline" onClick={onToggleFocus}>
            <Sparkles className="size-4" />
            {isFocused ? "Remove focus" : "Mark focus today"}
          </Button>
          <Button onClick={onToggleComplete}>
            {item.type === "bill" ? "Toggle paid state" : "Toggle complete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
