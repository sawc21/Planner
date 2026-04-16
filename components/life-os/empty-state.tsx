import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <Card className="border border-dashed hairline bg-transparent shadow-none">
      <CardContent className="flex flex-col items-start gap-3 p-5">
        <span className="rounded-2xl bg-[var(--surface-soft)] p-2 text-muted-foreground">
          <Icon className="size-4" />
        </span>
        <div className="space-y-1">
          <p className="font-medium text-foreground">{title}</p>
          <p className="text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
      </CardContent>
    </Card>
  );
}
