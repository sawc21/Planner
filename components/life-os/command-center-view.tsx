"use client";

import { Sparkles } from "lucide-react";

import { BuddyPanel } from "@/components/life-os/buddy-panel";
import { CommandConsole } from "@/components/life-os/command-console";
import { ConstraintCard } from "@/components/life-os/constraint-card";
import { OverloadWarningCard } from "@/components/life-os/overload-warning-card";
import { PageHeader } from "@/components/life-os/page-header";
import { RecommendationCard } from "@/components/life-os/recommendation-card";
import { Button } from "@/components/ui/button";
import {
  buildDailyNarrative,
  getBuddyInsight,
  getConstraintAwarePlan,
  getOverloadAssessment,
  getTodayRecommendations,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";

export function CommandCenterView() {
  const {
    workspaces,
    tasks,
    gradebooks,
    progressRecords,
    constraintProfile,
    openCommandPanel,
    completeTask,
    moveTaskToTomorrow,
    startTask,
  } = useLifeOs();

  const recommendations = getTodayRecommendations({
    workspaces,
    tasks,
    constraintProfile,
  });
  const overload = getOverloadAssessment({
    workspaces,
    tasks,
    constraintProfile,
  });
  const narrative = buildDailyNarrative({
    workspaces,
    tasks,
    constraintProfile,
    gradebooks,
    progressRecords,
  });
  const insight = getBuddyInsight({
    workspaces,
    tasks,
    constraintProfile,
    gradebooks,
    progressRecords,
  });
  const plan = getConstraintAwarePlan({
    workspaces,
    tasks,
    constraintProfile,
    gradebooks,
    progressRecords,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Command"
        title="A bounded command layer for the whole system."
        description="Use command for quick capture, plan generation, triage, and moving between workspace-specific flows without turning the product into chat."
        actions={
          <Button onClick={openCommandPanel}>
            <Sparkles className="size-4" />
            Open modal command
          </Button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <RecommendationCard
          recommendations={recommendations}
          onCompleteTask={completeTask}
          onMoveTaskToTomorrow={moveTaskToTomorrow}
          onStartTask={startTask}
        />
        <OverloadWarningCard assessment={overload} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-4">
          <CommandConsole embedded />
          <div className="rounded-[28px] bg-[var(--surface-soft)] p-5">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Narrative summary
            </p>
            <p className="mt-3 text-sm leading-7 text-foreground/82">{narrative}</p>
          </div>
        </div>
        <div className="space-y-4">
          <ConstraintCard constraintProfile={constraintProfile} />
          <BuddyPanel insight={insight} plan={plan} />
        </div>
      </div>
    </div>
  );
}
