"use client";
import { Files, GraduationCap, ListTodo, TrendingUp } from "lucide-react";

import { BuddyPanel } from "@/components/life-os/buddy-panel";
import { EmptyState } from "@/components/life-os/empty-state";
import { EventCard } from "@/components/life-os/event-card";
import { LifeItemCard } from "@/components/life-os/life-item-card";
import { PageHeader } from "@/components/life-os/page-header";
import { WorkspaceIcon } from "@/components/life-os/workspace-icon";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getBuddyInsight,
  getConstraintAwarePlan,
  getWorkspaceBundle,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";

export function WorkspaceDetailView({ workspaceId }: { workspaceId: string }) {
  const {
    workspaces,
    tasks,
    events,
    materials,
    gradebooks,
    progressRecords,
    constraintProfile,
    focusTodayIds,
    toggleFocusToday,
    completeTask,
    moveTaskToTomorrow,
    startTask,
  } = useLifeOs();

  const snapshot = {
    workspaces,
    tasks,
    events,
    materials,
    gradebooks,
    progressRecords,
    constraintProfile,
  };
  const bundle = getWorkspaceBundle(snapshot, workspaceId);

  if (!bundle) {
    return (
      <EmptyState
        title="Workspace not found"
        description="This workspace either does not exist yet or has not been loaded into the current local dataset."
      />
    );
  }

  const insight = getBuddyInsight(
    {
      workspaces,
      tasks,
      constraintProfile,
      gradebooks,
      progressRecords,
    },
    workspaceId,
  );
  const plan = getConstraintAwarePlan(
    {
      workspaces,
      tasks,
      constraintProfile,
      gradebooks,
      progressRecords,
    },
    workspaceId,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Workspace Detail"
        title={bundle.workspace.name}
        description={`${bundle.workspace.shortLabel} · ${bundle.workspace.ownerLabel} · ${bundle.workspace.progressSummary}`}
        actions={
          <div
            className={`inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium ${bundle.workspace.colorToken}`}
          >
            <WorkspaceIcon icon={bundle.workspace.icon} className="size-4" />
            {bundle.workspace.kind.replace("_", " ")}
          </div>
        }
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="surface-card border hairline xl:col-span-2">
          <CardContent className="grid gap-4 p-5 md:grid-cols-3">
            <div className="rounded-2xl bg-[var(--surface-soft)] p-4">
              <ListTodo className="size-5 text-primary" />
              <p className="mt-3 font-medium text-foreground">{bundle.tasks.length} linked tasks</p>
            </div>
            <div className="rounded-2xl bg-[var(--surface-soft)] p-4">
              <GraduationCap className="size-5 text-primary" />
              <p className="mt-3 font-medium text-foreground">{bundle.events.length} scheduled events</p>
            </div>
            <div className="rounded-2xl bg-[var(--surface-soft)] p-4">
              <Files className="size-5 text-primary" />
              <p className="mt-3 font-medium text-foreground">{bundle.materials.length} materials</p>
            </div>
          </CardContent>
        </Card>

        <Card className="surface-card border hairline">
          <CardHeader>
            <CardTitle className="font-heading text-2xl">Context snapshot</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-foreground/78">
            <p>{bundle.workspace.progressSummary}</p>
            {bundle.workspace.currentGrade != null ? (
              <p>Current grade: {bundle.workspace.currentGrade}%</p>
            ) : null}
            {bundle.workspace.creditHours ? <p>{bundle.workspace.creditHours} credit hours</p> : null}
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
          <TabsTrigger value="materials">Materials</TabsTrigger>
          <TabsTrigger value="progress">Progress</TabsTrigger>
          <TabsTrigger value="buddy">Buddy</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="grid gap-4 xl:grid-cols-2">
          <Card className="surface-card border hairline">
            <CardHeader>
              <CardTitle className="font-heading text-2xl">Next tasks</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {bundle.tasks.slice(0, 3).map((task) => (
                <LifeItemCard
                  key={task.id}
                  compact
                  item={task}
                  onCompleteTask={() => completeTask(task.id)}
                  onMoveTaskToTomorrow={() => moveTaskToTomorrow(task.id)}
                  onStartTask={() => startTask(task.id)}
                  onToggleFocus={() => toggleFocusToday(task.id)}
                  isFocused={focusTodayIds.includes(task.id)}
                />
              ))}
            </CardContent>
          </Card>

          <Card className="surface-card border hairline">
            <CardHeader>
              <CardTitle className="font-heading text-2xl">Upcoming events</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {bundle.events.length ? (
                bundle.events.map((event) => <EventCard key={event.id} event={event} compact />)
              ) : (
                <EmptyState
                  title="No events yet"
                  description="This workspace does not have scheduled sessions or appointments yet."
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tasks">
          <div className="space-y-3">
            {bundle.tasks.map((task) => (
              <LifeItemCard
                key={task.id}
                compact
                item={task}
                onCompleteTask={() => completeTask(task.id)}
                onMoveTaskToTomorrow={() => moveTaskToTomorrow(task.id)}
                onStartTask={() => startTask(task.id)}
                onToggleFocus={() => toggleFocusToday(task.id)}
                isFocused={focusTodayIds.includes(task.id)}
              />
            ))}
          </div>
        </TabsContent>

        <TabsContent value="materials">
          <div className="grid gap-4 xl:grid-cols-2">
            {bundle.materials.length ? (
              bundle.materials.map((material) => (
                <Card key={material.id} className="surface-card border hairline">
                  <CardHeader>
                    <CardTitle className="font-heading text-2xl">{material.title}</CardTitle>
                    <p className="text-sm leading-6 text-foreground/72">
                      {material.kind.replace("_", " ")} · {material.fileType}
                    </p>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-6 text-foreground/82">{material.summary}</p>
                  </CardContent>
                </Card>
              ))
            ) : (
              <EmptyState
                title="No materials yet"
                description="Add notes, guides, or specs to give this workspace more context."
              />
            )}
          </div>
        </TabsContent>

        <TabsContent value="progress" className="grid gap-4 xl:grid-cols-2">
          {bundle.gradebook ? (
            <Card className="surface-card border hairline">
              <CardHeader>
                <CardTitle className="font-heading text-2xl">Gradebook</CardTitle>
                <p className="text-sm leading-6 text-foreground/72">
                  Current grade {bundle.gradebook.currentGrade}% against a target of {bundle.gradebook.targetGrade}%.
                </p>
              </CardHeader>
              <CardContent className="space-y-3">
                {bundle.gradebook.categories.map((category) => (
                  <div key={category.id} className="rounded-2xl bg-[var(--surface-soft)] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium text-foreground">{category.label}</p>
                      <span className="rounded-full bg-white/80 px-3 py-1 text-xs text-muted-foreground">
                        {category.weight}% weight
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-foreground/72">
                      Current category score: {category.currentScore}%
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}

          <Card className="surface-card border hairline">
            <CardHeader>
              <CardTitle className="font-heading text-2xl">Progress signals</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {bundle.progress.length ? (
                bundle.progress.map((record) => (
                  <div key={record.id} className="rounded-2xl bg-[var(--surface-soft)] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium text-foreground">{record.label}</p>
                      <span className="rounded-full bg-white/80 px-3 py-1 text-xs text-muted-foreground">
                        {record.currentValue}/{record.targetValue} {record.unit}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-foreground/72">
                      Confidence is currently {record.confidence}.
                    </p>
                  </div>
                ))
              ) : (
                <EmptyState
                  icon={TrendingUp}
                  title="No progress metrics yet"
                  description="This workspace has context, but not a custom progress board yet."
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="buddy">
          <BuddyPanel insight={insight} plan={plan} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
