"use client";

import { useMemo, useState } from "react";

import { BuddyPanel } from "@/components/life-os/buddy-panel";
import { EmptyState } from "@/components/life-os/empty-state";
import { PageHeader } from "@/components/life-os/page-header";
import { FilterChip } from "@/components/life-os/filter-chip";
import { WorkspaceCard } from "@/components/life-os/workspace-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAtRiskWorkspaces, getBuddyInsight, getConstraintAwarePlan } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";

type WorkspaceView = "all" | "course" | "project" | "at-risk" | "active";

export function WorkspacesView({
  initialType = "",
}: {
  initialType?: string;
}) {
  const { workspaces, tasks, events, materials, milestones, gradebooks, constraintProfile } = useLifeOs();
  const [activeView, setActiveView] = useState<WorkspaceView>(
    initialType === "course" || initialType === "project" ? (initialType as WorkspaceView) : "all",
  );
  const atRisk = getAtRiskWorkspaces({ workspaces, tasks, gradebooks, milestones });
  const riskMap = useMemo(() => new Map(atRisk.map((entry) => [entry.workspace.id, entry])), [atRisk]);
  const visibleWorkspaces = useMemo(() => {
    const sorted = [...workspaces].sort((a, b) => (riskMap.get(b.id)?.score ?? 0) - (riskMap.get(a.id)?.score ?? 0) || a.name.localeCompare(b.name));

    if (activeView === "course" || activeView === "project") {
      return sorted.filter((workspace) => workspace.kind === activeView);
    }
    if (activeView === "at-risk") {
      return sorted.filter((workspace) => riskMap.has(workspace.id));
    }
    if (activeView === "active") {
      return sorted.filter((workspace) => workspace.active);
    }
    return sorted;
  }, [activeView, riskMap, workspaces]);
  const leadWorkspace = visibleWorkspaces[0];
  const buddyInsight = getBuddyInsight(
    {
      workspaces,
      tasks,
      events,
      materials,
      milestones,
      widgets: [],
      constraintProfile,
      gradebooks,
    },
    leadWorkspace?.id,
  );
  const plan = getConstraintAwarePlan({ workspaces, tasks, constraintProfile }, leadWorkspace?.id);

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Workspaces"
        title="Orbit groups the board by active context."
        description="Courses and projects share one operational surface so risk, momentum, and workload stay visible in the same frame."
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.45fr)_300px]">
        <div className="space-y-3">
          <div className="surface-panel rounded-xl border hairline p-3.5 sm:p-4">
            <div className="flex flex-wrap gap-2">
              {([
                ["all", "All"],
                ["course", "Courses"],
                ["project", "Projects"],
                ["at-risk", "At Risk"],
                ["active", "Active"],
              ] as const).map(([value, label]) => (
                <FilterChip key={value} active={activeView === value} onClick={() => setActiveView(value)}>
                  {label}
                </FilterChip>
              ))}
            </div>
          </div>

          {visibleWorkspaces.length ? (
            <div className="grid gap-3 xl:grid-cols-2">
              {visibleWorkspaces.map((workspace) => (
                <WorkspaceCard
                  key={workspace.id}
                  workspace={workspace}
                  href={`/workspaces/${workspace.id}`}
                  taskCount={tasks.filter((task) => task.primaryWorkspaceId === workspace.id || task.linkedWorkspaceIds.includes(workspace.id)).filter((task) => task.status !== "done" && task.status !== "paid").length}
                  eventCount={events.filter((event) => event.workspaceId === workspace.id).length}
                  materialCount={materials.filter((material) => material.workspaceId === workspace.id).length + milestones.filter((milestone) => milestone.workspaceId === workspace.id).length}
                  risk={riskMap.get(workspace.id)}
                />
              ))}
            </div>
          ) : (
            <EmptyState title="No workspaces match that filter" description="Switch filters to widen the board again." />
          )}
        </div>

        <aside className="space-y-3">
          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Workspace summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5 text-[12px] text-muted-foreground">
              <p>
                {leadWorkspace
                  ? `${leadWorkspace.shortLabel} is the strongest visible workspace in this filter.`
                  : "The current filter has no visible workspaces."}
              </p>
              {leadWorkspace ? (
                <div className="rounded-xl border hairline bg-[var(--surface-soft)]/86 p-3">
                  <p className="font-medium text-foreground">{leadWorkspace.name}</p>
                  <p className="mt-1 text-[11px] leading-5 text-muted-foreground">{leadWorkspace.progressSummary}</p>
                </div>
              ) : null}
            </CardContent>
          </Card>
          <BuddyPanel insight={buddyInsight} plan={plan} />
        </aside>
      </div>
    </div>
  );
}

