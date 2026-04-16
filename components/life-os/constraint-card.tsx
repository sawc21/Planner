import { BatteryCharging, CircleDollarSign, Timer } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ConstraintProfile } from "@/lib/life-os/types";

export function ConstraintCard({
  constraintProfile,
}: {
  constraintProfile: ConstraintProfile;
}) {
  return (
    <Card className="surface-card rounded-xl border hairline">
      <CardHeader>
        <CardTitle className="text-xl font-semibold tracking-tight">Constraint profile</CardTitle>
        <p className="text-[13px] leading-5 text-foreground/72">
          Light budget, time, and energy constraints that shape the study and life flow.
        </p>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
          <Timer className="size-4 text-primary" />
          <p className="mt-2.5 text-[13px] font-medium text-foreground">
            <span className="font-mono">{constraintProfile.hoursRemainingThisWeek}</span> hours left
          </p>
          <p className="mt-1 text-[12px] text-foreground/72">
            Out of <span className="font-mono">{constraintProfile.weeklyHoursAvailable}</span> hours available this week.
          </p>
        </div>
        <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
          <CircleDollarSign className="size-4 text-primary" />
          <p className="mt-2.5 text-[13px] font-medium text-foreground">
            <span className="font-mono">${constraintProfile.budgetRemainingThisWeek}</span> remaining
          </p>
          <p className="mt-1 text-[12px] text-foreground/72">
            Out of <span className="font-mono">${constraintProfile.weeklyBudgetAvailable}</span> budgeted for the week.
          </p>
        </div>
        <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
          <BatteryCharging className="size-4 text-primary" />
          <p className="mt-2.5 text-[13px] font-medium text-foreground">
            {constraintProfile.defaultEnergyProfile} default energy
          </p>
          <p className="mt-1 text-[12px] text-foreground/72">
            Planning favors tasks that fit this energy profile first.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
