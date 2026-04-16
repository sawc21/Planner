import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
}) {
  return (
    <Card className="surface-card border hairline">
      <CardContent className="flex items-start justify-between gap-4 p-4">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            {label}
          </p>
          <p className="text-2xl font-semibold tracking-tight text-foreground">
            {value}
          </p>
          <p className="text-sm text-muted-foreground">{detail}</p>
        </div>
        <span className="rounded-2xl bg-[var(--surface-soft)] p-2 text-primary">
          <Icon className="size-4" />
        </span>
      </CardContent>
    </Card>
  );
}
