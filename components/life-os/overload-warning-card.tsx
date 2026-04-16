import { AlertTriangle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OverloadAssessment } from "@/lib/life-os/types";

export function OverloadWarningCard({
  assessment,
}: {
  assessment: OverloadAssessment;
}) {
  return (
    <Card
      className={
        assessment.isOverloaded
          ? "border-none bg-[var(--attention-soft)] shadow-none"
          : "border hairline bg-[var(--success-soft)] shadow-none"
      }
    >
      <CardHeader className="flex flex-row items-start gap-3 space-y-0">
        <span className="rounded-2xl bg-white/65 p-2 text-foreground">
          <AlertTriangle className="size-4" />
        </span>
        <div className="space-y-1">
          <CardTitle className="font-heading text-2xl">
            {assessment.isOverloaded ? "Gentle overload warning" : "Load looks workable"}
          </CardTitle>
          <p className="text-sm leading-6 text-foreground/80">{assessment.reason}</p>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-6 text-foreground/80">{assessment.suggestedAction}</p>
      </CardContent>
    </Card>
  );
}
