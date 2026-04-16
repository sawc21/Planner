"use client";

import { useMemo, useState } from "react";

import { EmptyState } from "@/components/life-os/empty-state";
import { PageHeader } from "@/components/life-os/page-header";
import { WorkspaceCard } from "@/components/life-os/workspace-card";
import { FilterChip } from "@/components/life-os/filter-chip";
import { getAtRiskWorkspaces } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import type { WorkspaceKind } from "@/lib/life-os/types";

export function WorkspacesView({
  initialView = "",
}: {
  initialView?: string;
}) {
  const { workspaces, tasks, gradebooks, progressRecords, materials, events } = useLifeOs();
  const defaultKind = initialView === "at-risk" ? "all" : "all";
  const [activeKind, setActiveKind] = useState<WorkspaceKind | "all">(defaultKind);
  const atRisk = getAtRiskWorkspaces({ workspaces, tasks, gradebooks, progressRecords });
  const riskMap = useMemo(
    () => new Map(atRisk.map((entry) => [entry.workspace.id, entry])),
    [atRisk],
  );

  const visibleWorkspaces = [...workspaces]
    .filter((workspace) => activeKind === "all" || workspace.kind === activeKind)
    .sort((a, b) => {
      if (initialView === "at-risk") {
        return (riskMap.get(b.id)?.score ?? 0) - (riskMap.get(a.id)?.score ?? 0);
      }

      return a.name.localeCompare(b.name);
    });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Workspaces"
        title="Context first, not just tasks."
        description="Courses, study tracks, personal admin, work, and life flows each get their own identity so the system knows where every task and material belongs."
      />

      <div className="surface-panel rounded-[28px] border hairline p-4 sm:p-5">
        <div className="flex flex-wrap gap-2">
          <FilterChip active={activeKind === "all"} onClick={() => setActiveKind("all")}>
            All
          </FilterChip>
          {(["course", "study_track", "personal", "work", "admin"] as WorkspaceKind[]).map((kind) => (
            <FilterChip
              key={kind}
              active={activeKind === kind}
              onClick={() => setActiveKind(kind)}
            >
              {kind.replace("_", " ")}
            </FilterChip>
          ))}
        </div>
      </div>

      {visibleWorkspaces.length ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {visibleWorkspaces.map((workspace) => (
            <WorkspaceCard
              key={workspace.id}
              workspace={workspace}
              href={`/workspaces/${workspace.id}`}
              taskCount={tasks.filter((task) => task.workspaceId === workspace.id && task.status !== "done" && task.status !== "paid").length}
              eventCount={events.filter((event) => event.workspaceId === workspace.id).length}
              materialCount={materials.filter((material) => material.workspaceId === workspace.id).length}
              risk={riskMap.get(workspace.id)}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No workspaces match that filter"
          description="Switch back to the full workspace board to widen the view again."
        />
      )}
    </div>
  );
}
