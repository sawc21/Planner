import { BatteryCharging, CircleDollarSign, Timer } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ConstraintProfile } from "@/lib/life-os/types";

export function ConstraintCard({
  constraintProfile,
}: {
  constraintProfile: ConstraintProfile;
}) {
  return (
    <Card className="surface-card border hairline">
      <CardHeader>
        <CardTitle className="font-heading text-2xl">Constraint profile</CardTitle>
        <p className="text-sm leading-6 text-foreground/72">
          Light budget, time, and energy constraints that shape the study and life flow.
        </p>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl bg-[var(--surface-soft)] p-4">
          <Timer className="size-5 text-primary" />
          <p className="mt-3 font-medium text-foreground">
            {constraintProfile.hoursRemainingThisWeek} hours left
          </p>
          <p className="mt-1 text-sm text-foreground/72">
            Out of {constraintProfile.weeklyHoursAvailable} hours available this week.
          </p>
        </div>
        <div className="rounded-2xl bg-[var(--surface-soft)] p-4">
          <CircleDollarSign className="size-5 text-primary" />
          <p className="mt-3 font-medium text-foreground">
            ${constraintProfile.budgetRemainingThisWeek} remaining
          </p>
          <p className="mt-1 text-sm text-foreground/72">
            Out of ${constraintProfile.weeklyBudgetAvailable} budgeted for the week.
          </p>
        </div>
        <div className="rounded-2xl bg-[var(--surface-soft)] p-4">
          <BatteryCharging className="size-5 text-primary" />
          <p className="mt-3 font-medium text-foreground">
            {constraintProfile.defaultEnergyProfile} default energy
          </p>
          <p className="mt-1 text-sm text-foreground/72">
            Planning favors tasks that fit this energy profile first.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
