import { Badge } from "@/components/ui/badge";
import type { LifeItem } from "@/lib/life-os/types";
import { PRIORITY_LABELS, STATUS_LABELS, TYPE_LABELS } from "@/lib/life-os/types";

const TYPE_STYLES: Record<LifeItem["type"], string> = {
  task: "bg-[var(--surface-soft)] text-foreground",
  bill: "bg-[var(--attention-soft)] text-foreground",
  appointment: "bg-[var(--success-soft)] text-foreground",
  reminder: "bg-[var(--surface-soft)] text-muted-foreground",
  errand: "bg-[var(--surface-strong)] text-foreground",
};

const PRIORITY_STYLES: Record<LifeItem["priority"], string> = {
  low: "bg-[var(--surface-soft)] text-muted-foreground",
  medium: "bg-[var(--surface-strong)] text-foreground",
  high: "bg-[var(--attention-soft)] text-foreground",
  critical: "bg-[var(--danger-soft)] text-foreground",
};

const STATUS_STYLES: Record<LifeItem["status"], string> = {
  todo: "bg-transparent text-muted-foreground ring-1 ring-border",
  in_progress: "bg-[var(--surface-strong)] text-foreground",
  done: "bg-[var(--success-soft)] text-foreground",
  scheduled: "bg-[var(--surface-soft)] text-foreground",
  paid: "bg-[var(--success-soft)] text-foreground",
  snoozed: "bg-[var(--attention-soft)] text-foreground",
};

export function ItemPillBadges({ item }: { item: LifeItem }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge className={TYPE_STYLES[item.type]}>{TYPE_LABELS[item.type]}</Badge>
      <Badge className={PRIORITY_STYLES[item.priority]}>
        {PRIORITY_LABELS[item.priority]}
      </Badge>
      <Badge className={STATUS_STYLES[item.status]}>
        {STATUS_LABELS[item.status]}
      </Badge>
    </div>
  );
}
