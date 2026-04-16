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
    <Card className="surface-card rounded-xl border hairline">
      <CardContent className="flex items-start justify-between gap-4 p-4">
        <div className="space-y-1">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
            {label}
          </p>
          <p className="font-mono text-2xl font-semibold tracking-tight text-foreground">
            {value}
          </p>
          <p className="text-[12px] text-muted-foreground">{detail}</p>
        </div>
        <span className="rounded-md bg-primary/10 p-2 text-primary">
          <Icon className="size-4" />
        </span>
      </CardContent>
    </Card>
  );
}
