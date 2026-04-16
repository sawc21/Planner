"use client";

import Link from "next/link";
import { BookOpen, Files, Flag, GraduationCap, ListTodo, Sparkles } from "lucide-react";

import { BuddyPanel } from "@/components/life-os/buddy-panel";
import { EmptyState } from "@/components/life-os/empty-state";
import { EventCard } from "@/components/life-os/event-card";
import { LifeItemCard } from "@/components/life-os/life-item-card";
import { PageHeader } from "@/components/life-os/page-header";
import { WorkspaceIcon } from "@/components/life-os/workspace-icon";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getBuddyInsight, getConstraintAwarePlan, getWorkspaceBundle } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

export function WorkspaceDetailView({ workspaceId }: { workspaceId: string }) {
  const {
    workspaces,
    tasks,
    events,
    materials,
    milestones,
    gradebooks,
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
    milestones,
    widgets: [],
    gradebooks,
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

  const insight = getBuddyInsight(snapshot, workspaceId);
  const plan = getConstraintAwarePlan({ workspaces, tasks, constraintProfile }, workspaceId);
  const isCourse = bundle.workspace.kind === "course";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Workspace"
        title={bundle.workspace.name}
        description={`${bundle.workspace.shortLabel} · ${bundle.workspace.ownerLabel} · ${bundle.workspace.progressSummary}`}
      />

      <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)_340px]">
        <aside className="space-y-4">
          <Card className="surface-card rounded-xl border hairline">
            <CardHeader>
              <div className="flex items-center gap-3">
                <span className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 ${bundle.workspace.colorToken}`}>
                  <WorkspaceIcon icon={bundle.workspace.icon} className="size-4" />
                  <span className="font-mono text-[11px] font-medium uppercase tracking-[0.18em]">{bundle.workspace.shortLabel}</span>
                </span>
              </div>
              <CardTitle className="text-xl font-semibold tracking-tight">Identity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-[13px] text-muted-foreground">
              <p>{bundle.workspace.progressSummary}</p>
              <p>{bundle.workspace.ownerLabel}</p>
              {bundle.workspace.currentGrade != null ? <p>Current grade: <span className="font-mono text-foreground">{bundle.workspace.currentGrade}%</span></p> : null}
              {bundle.workspace.creditHours ? <p>{bundle.workspace.creditHours} credit hours</p> : null}
            </CardContent>
          </Card>

          <Card className="surface-card rounded-xl border hairline">
            <CardHeader>
              <CardTitle className="text-xl font-semibold tracking-tight">Prompt chips</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Link href="/assistant?intent=focus_workspace" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                Focus workspace
              </Link>
              <Link href="/assistant?intent=generate_weekly_plan" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                Generate plan
              </Link>
              <Link href="/assistant?intent=explain_priority" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                Explain priority
              </Link>
            </CardContent>
          </Card>
        </aside>

        <div className="space-y-4">
          <Card className="surface-panel rounded-2xl border-none">
            <CardContent className="grid gap-3 p-5 md:grid-cols-3">
              <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
                <ListTodo className="size-4 text-primary" />
                <p className="mt-2.5 text-[13px] font-medium text-foreground">
                  <span className="font-mono">{bundle.tasks.length}</span> linked tasks
                </p>
              </div>
              <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
                <GraduationCap className="size-4 text-primary" />
                <p className="mt-2.5 text-[13px] font-medium text-foreground">
                  <span className="font-mono">{bundle.events.length}</span> scheduled events
                </p>
              </div>
              <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
                <Files className="size-4 text-primary" />
                <p className="mt-2.5 text-[13px] font-medium text-foreground">
                  <span className="font-mono">{bundle.materials.length + bundle.milestones.length}</span> context items
                </p>
              </div>
            </CardContent>
          </Card>

          <Tabs defaultValue="overview" className="space-y-4">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="assignments">Assignments</TabsTrigger>
              <TabsTrigger value={isCourse ? "materials" : "milestones"}>{isCourse ? "Materials" : "Milestones"}</TabsTrigger>
              <TabsTrigger value="progress">{isCourse ? "Grade Summary" : "Progress"}</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="grid gap-4 xl:grid-cols-2">
              <Card className="surface-card rounded-xl border hairline">
                <CardHeader>
                  <CardTitle className="text-xl font-semibold tracking-tight">Next work</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {bundle.tasks.length ? bundle.tasks.slice(0, 4).map((task) => (
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
                  )) : <EmptyState title="No linked work yet" description="Orbit has not attached tasks to this workspace yet." />}
                </CardContent>
              </Card>

              <Card className="surface-card rounded-xl border hairline">
                <CardHeader>
                  <CardTitle className="text-xl font-semibold tracking-tight">Upcoming events</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {bundle.events.length ? bundle.events.map((event) => <EventCard key={event.id} event={event} compact />) : <EmptyState title="No scheduled events" description="This workspace does not have visible events yet." />}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="assignments" className="space-y-3">
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
            </TabsContent>

            <TabsContent value={isCourse ? "materials" : "milestones"} className="grid gap-4 xl:grid-cols-2">
              {isCourse
                ? bundle.materials.length
                  ? bundle.materials.map((material) => (
                      <Card key={material.id} className="surface-card rounded-xl border hairline">
                        <CardHeader>
                          <CardTitle className="text-xl font-semibold tracking-tight">{material.title}</CardTitle>
                          <p className="text-sm leading-6 text-foreground/72">{material.kind.replace("_", " ")} · {material.fileType}</p>
                        </CardHeader>
                        <CardContent>
                          <p className="text-sm leading-6 text-foreground/82">{material.summary}</p>
                        </CardContent>
                      </Card>
                    ))
                  : <EmptyState title="No materials yet" description="Add notes, guides, or specs to give this course more context." />
                : bundle.milestones.length
                  ? bundle.milestones.map((milestone) => (
                      <Card key={milestone.id} className="surface-card rounded-xl border hairline">
                        <CardHeader>
                          <CardTitle className="text-xl font-semibold tracking-tight">{milestone.title}</CardTitle>
                          <p className="text-sm leading-6 text-foreground/72">{milestone.summary}</p>
                        </CardHeader>
                        <CardContent className="space-y-3">
                          <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
                            <Flag className="size-4 text-primary" />
                            <p className="mt-2 text-[13px] font-medium text-foreground">{milestone.progressPercent}% complete</p>
                            <p className="mt-1 text-[12px] text-muted-foreground">Status: {milestone.status.replace("_", " ")}</p>
                          </div>
                        </CardContent>
                      </Card>
                    ))
                  : <EmptyState title="No milestones yet" description="Add milestones to give this project a visible shipping path." />}
            </TabsContent>

            <TabsContent value="progress" className="grid gap-4 xl:grid-cols-2">
              {isCourse ? (
                <Card className="surface-card rounded-xl border hairline">
                  <CardHeader>
                    <CardTitle className="text-xl font-semibold tracking-tight">Grade summary</CardTitle>
                    <p className="text-[13px] leading-5 text-foreground/72">Current grade <span className="font-mono">{bundle.gradebook?.currentGrade ?? bundle.workspace.currentGrade}%</span> against a target of <span className="font-mono">{bundle.gradebook?.targetGrade ?? bundle.workspace.targetGrade}%</span>.</p>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {bundle.gradebook?.categories.map((category) => (
                      <div key={category.id} className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[13px] font-medium text-foreground">{category.label}</p>
                          <span className="rounded-md border hairline bg-card/80 px-2 py-0.5 font-mono text-[11px] text-muted-foreground">{category.weight}% weight</span>
                        </div>
                        <p className="mt-2 text-[12px] text-foreground/72">Current category score: <span className="font-mono">{category.currentScore}%</span></p>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : (
                <Card className="surface-card rounded-xl border hairline">
                  <CardHeader>
                    <CardTitle className="text-xl font-semibold tracking-tight">Progress summary</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {bundle.milestones.map((milestone) => (
                      <div key={milestone.id} className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
                        <p className="text-[13px] font-medium text-foreground">{milestone.title}</p>
                        <p className="mt-1 text-[12px] text-muted-foreground">{milestone.progressPercent}% complete</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              <Card className="surface-card rounded-xl border hairline">
                <CardHeader>
                  <CardTitle className="text-xl font-semibold tracking-tight">Assistant result</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-[13px] text-muted-foreground">
                  <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3.5">
                    <BookOpen className="size-4 text-primary" />
                    <p className="mt-2 text-foreground">{insight.summary}</p>
                  </div>
                  <Link href="/assistant" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-fit")}>
                    <Sparkles className="size-4" />
                    Open assistant
                  </Link>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        <aside className="space-y-4">
          <BuddyPanel insight={insight} plan={plan} />
          <Card className="surface-card rounded-xl border hairline">
            <CardHeader>
              <CardTitle className="text-xl font-semibold tracking-tight">Inline results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[13px] text-muted-foreground">
              {insight.bullets.map((bullet) => (
                <div key={bullet} className="rounded-lg bg-[var(--surface-soft)] p-3">{bullet}</div>
              ))}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

