import { AlertTriangle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OverloadAssessment } from "@/lib/life-os/types";

export function OverloadWarningCard({
  assessment,
}: {
  assessment: OverloadAssessment;
}) {
  const styleBySeverity = {
    overloaded: "border-none bg-[var(--attention-soft)] ring-1 ring-amber-400/30",
    watch: "border hairline bg-[var(--surface-soft)] ring-1 ring-primary/10",
    calm: "border hairline bg-[var(--success-soft)]",
  } as const;

  return (
    <Card
      className={`${styleBySeverity[assessment.severity]} rounded-xl shadow-none transition-colors duration-300 animate-in fade-in-0`}
    >
      <CardHeader className="flex flex-row items-start gap-3 space-y-0">
        <span className="rounded-md bg-card/70 p-2 text-foreground">
          <AlertTriangle className="size-4" />
        </span>
        <div className="space-y-1">
          <CardTitle className="text-xl font-semibold tracking-tight">
            {assessment.severity === "overloaded"
              ? "Gentle overload warning"
              : assessment.severity === "watch"
                ? "Keep an eye on today's load"
                : "Load looks workable"}
          </CardTitle>
          <p className="text-[13px] leading-5 text-foreground/82">{assessment.reason}</p>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-[13px] leading-5 text-foreground/82">{assessment.suggestedAction}</p>
      </CardContent>
    </Card>
  );
}
