import { Badge } from "@/components/ui/badge";
import type { TaskView } from "@/lib/life-os/types";
import {
  TASK_KIND_LABELS,
  TASK_PRIORITY_LABELS,
  TASK_STATUS_LABELS,
  WORKSPACE_KIND_LABELS,
} from "@/lib/life-os/types";

const KIND_STYLES: Record<TaskView["kind"], string> = {
  assignment: "bg-[var(--attention-soft)] text-foreground",
  study_session: "bg-[var(--success-soft)] text-foreground",
  admin: "bg-[var(--surface-soft)] text-foreground",
  bill: "bg-[var(--danger-soft)] text-foreground",
  errand: "bg-[var(--surface-strong)] text-foreground",
  work_task: "bg-[var(--surface-soft)] text-foreground",
};

const PRIORITY_STYLES: Record<TaskView["priority"], string> = {
  low: "bg-[var(--surface-soft)] text-muted-foreground",
  medium: "bg-[var(--surface-strong)] text-foreground",
  high: "bg-[var(--attention-soft)] text-foreground",
  critical: "bg-[var(--danger-soft)] text-foreground",
};

const STATUS_STYLES: Record<TaskView["status"], string> = {
  todo: "bg-transparent text-muted-foreground ring-1 ring-border",
  in_progress: "bg-[var(--surface-strong)] text-foreground",
  done: "bg-[var(--success-soft)] text-foreground",
  scheduled: "bg-[var(--surface-soft)] text-foreground",
  paid: "bg-[var(--success-soft)] text-foreground",
  snoozed: "bg-[var(--attention-soft)] text-foreground",
};

export function ItemPillBadges({ item }: { item: TaskView }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge className={item.workspace.colorToken}>{item.workspace.shortLabel}</Badge>
      <Badge className="bg-[var(--surface-soft)] text-foreground">
        {WORKSPACE_KIND_LABELS[item.workspace.kind]}
      </Badge>
      <Badge className={KIND_STYLES[item.kind]}>{TASK_KIND_LABELS[item.kind]}</Badge>
      <Badge className={PRIORITY_STYLES[item.priority]}>
        {TASK_PRIORITY_LABELS[item.priority]}
      </Badge>
      <Badge className={STATUS_STYLES[item.status]}>
        {TASK_STATUS_LABELS[item.status]}
      </Badge>
    </div>
  );
}
