"use client";

import { useDeferredValue, useState } from "react";
import Link from "next/link";
import { Search, SlidersHorizontal } from "lucide-react";

import { EmptyState } from "@/components/life-os/empty-state";
import { FilterChip } from "@/components/life-os/filter-chip";
import { PageHeader } from "@/components/life-os/page-header";
import { BuddyPanel } from "@/components/life-os/buddy-panel";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getBuddyInsight,
  getConstraintAwarePlan,
  getOverdueTasks,
  getTaskViews,
  getTodayTasks,
  getUpcomingTasks,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import type { AssignmentFilterState, TaskScope, TaskView } from "@/lib/life-os/types";
import {
  TASK_KIND_LABELS,
  TASK_KINDS,
  TASK_PRIORITY_LABELS,
  TASK_PRIORITIES,
  TASK_STATUSES,
  TASK_STATUS_LABELS,
} from "@/lib/life-os/types";
import { cn } from "@/lib/utils";

function getInitialFilters(searchParams: URLSearchParams): AssignmentFilterState {
  return {
    scope: (searchParams.get("scope") as TaskScope | null) ?? "all",
    workspaceId: searchParams.get("workspaceId") ?? "all",
    kind: (searchParams.get("kind") as AssignmentFilterState["kind"] | null) ?? "all",
    status: (searchParams.get("status") as AssignmentFilterState["status"] | null) ?? "all",
    priority: (searchParams.get("priority") as AssignmentFilterState["priority"] | null) ?? "all",
    query: searchParams.get("query") ?? "",
  };
}

function applyScope(
  items: TaskView[],
  scopes: {
    today: TaskView[];
    overdue: TaskView[];
    upcoming: TaskView[];
  },
  scope: TaskScope,
) {
  if (scope === "today") {
    const ids = new Set(scopes.today.map((item) => item.id));
    return items.filter((item) => ids.has(item.id));
  }
  if (scope === "overdue") {
    const ids = new Set(scopes.overdue.map((item) => item.id));
    return items.filter((item) => ids.has(item.id));
  }
  if (scope === "upcoming") {
    const ids = new Set(scopes.upcoming.map((item) => item.id));
    return items.filter((item) => ids.has(item.id));
  }

  return items;
}

export function TasksView({ initialQueryString = "" }: { initialQueryString?: string }) {
  const {
    workspaces,
    tasks,
    events,
    materials,
    milestones,
    widgets,
    gradebooks,
    constraintProfile,
    completeTask,
    moveTaskToTomorrow,
    startTask,
  } = useLifeOs();
  const [filters, setFilters] = useState<AssignmentFilterState>(() =>
    getInitialFilters(new URLSearchParams(initialQueryString)),
  );
  const deferredQuery = useDeferredValue(filters.query);
  const taskViews = getTaskViews({ tasks, workspaces });
  const scopedTasks = {
    today: getTodayTasks({ tasks, workspaces }),
    overdue: getOverdueTasks({ tasks, workspaces }),
    upcoming: getUpcomingTasks({ tasks, workspaces }),
  };
  const filteredItems = applyScope(taskViews, scopedTasks, filters.scope).filter((item) => {
    if (filters.workspaceId !== "all" && item.workspace?.id !== filters.workspaceId) {
      return false;
    }
    if (filters.kind !== "all" && item.kind !== filters.kind) {
      return false;
    }
    if (filters.status !== "all" && item.status !== filters.status) {
      return false;
    }
    if (filters.priority !== "all" && item.priority !== filters.priority) {
      return false;
    }
    if (deferredQuery) {
      const haystack = `${item.title} ${item.notes ?? ""} ${item.workspace?.name ?? ""} ${item.tags.join(" ")}`.toLowerCase();
      return haystack.includes(deferredQuery.toLowerCase());
    }
    return true;
  });
  const buddyInsight = getBuddyInsight({
    workspaces,
    tasks,
    events,
    materials,
    milestones,
    widgets,
    constraintProfile,
    gradebooks,
  });
  const plan = getConstraintAwarePlan({ workspaces, tasks, constraintProfile });

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Assignments"
        title="Run the operational board without losing context."
        description="Assignments, study sessions, project tasks, and admin work stay in one dense lane with immediate row actions and workspace links."
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.45fr)_300px]">
        <div className="space-y-3">
          <div className="surface-panel rounded-xl border hairline p-3.5 sm:p-4">
            <div className="flex flex-col gap-3">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={filters.query}
                  onChange={(event) => setFilters((current) => ({ ...current, query: event.target.value }))}
                  placeholder="Search assignments, notes, workspaces, or tags"
                  className="h-10 rounded-xl bg-background/70 pl-10"
                />
              </div>

              <div className="grid gap-3 sm:grid-cols-3 xl:flex xl:items-center">
                <Select value={filters.workspaceId} onValueChange={(value) => setFilters((current) => ({ ...current, workspaceId: value as AssignmentFilterState["workspaceId"] }))}>
                  <SelectTrigger className="w-full rounded-xl bg-background/70 sm:w-[220px]">
                    <SelectValue placeholder="All workspaces" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All workspaces</SelectItem>
                    {workspaces.map((workspace) => (
                      <SelectItem key={workspace.id} value={workspace.id}>
                        {workspace.shortLabel} · {workspace.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={filters.status} onValueChange={(value) => setFilters((current) => ({ ...current, status: value as AssignmentFilterState["status"] }))}>
                  <SelectTrigger className="w-full rounded-xl bg-background/70 sm:w-[180px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All statuses</SelectItem>
                    {TASK_STATUSES.map((status) => (
                      <SelectItem key={status} value={status}>
                        {TASK_STATUS_LABELS[status]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={filters.priority} onValueChange={(value) => setFilters((current) => ({ ...current, priority: value as AssignmentFilterState["priority"] }))}>
                  <SelectTrigger className="w-full rounded-xl bg-background/70 sm:w-[180px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All priorities</SelectItem>
                    {TASK_PRIORITIES.map((priority) => (
                      <SelectItem key={priority} value={priority}>
                        {TASK_PRIORITY_LABELS[priority]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <SlidersHorizontal className="size-4" />
                  Scope
                </span>
                {(["all", "today", "overdue", "upcoming"] as TaskScope[]).map((scope) => (
                  <FilterChip key={scope} active={filters.scope === scope} onClick={() => setFilters((current) => ({ ...current, scope }))}>
                    {scope === "all" ? "Everything" : scope === "today" ? "Today" : scope === "overdue" ? "Overdue" : "Upcoming"}
                  </FilterChip>
                ))}
                {TASK_KINDS.map((kind) => (
                  <FilterChip key={kind} active={filters.kind === kind} onClick={() => setFilters((current) => ({ ...current, kind: current.kind === kind ? "all" : kind }))}>
                    {TASK_KIND_LABELS[kind]}
                  </FilterChip>
                ))}
              </div>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border hairline bg-background/66">
            <div className="grid grid-cols-[minmax(0,1.8fr)_110px_96px_110px_180px] gap-3 border-b hairline px-3 py-2.5 text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              <span>Assignment</span>
              <span>Status</span>
              <span>Priority</span>
              <span>Workspace</span>
              <span>Actions</span>
            </div>
            {filteredItems.length ? (
              filteredItems.map((item) => (
                <div key={item.id} className="grid grid-cols-[minmax(0,1.8fr)_110px_96px_110px_180px] gap-3 border-b hairline px-3 py-2.5 text-[12px] last:border-b-0">
                  <div>
                    <Link href={item.workspace?.id ? `/workspaces/${item.workspace.id}` : "/assistant"} className="font-medium text-foreground hover:text-primary">
                      {item.title}
                    </Link>
                    <p className="mt-1 text-[11px] leading-4 text-muted-foreground">{item.notes ?? "No note attached."}</p>
                  </div>
                  <span className="text-muted-foreground">{TASK_STATUS_LABELS[item.status]}</span>
                  <span className="text-muted-foreground">{TASK_PRIORITY_LABELS[item.priority]}</span>
                  <span className="text-muted-foreground">{item.workspace?.shortLabel ?? "GENERAL"}</span>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => startTask(item.id)} className="text-[11px] font-medium text-primary">Start</button>
                    <button type="button" onClick={() => moveTaskToTomorrow(item.id)} className="text-[11px] font-medium text-primary">Tomorrow</button>
                    <button type="button" onClick={() => completeTask(item.id)} className="text-[11px] font-medium text-primary">Done</button>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-5">
                <EmptyState title="No assignments match that filter" description="Relax one filter or widen the scope to rebuild the board." />
              </div>
            )}
          </div>
        </div>

        <aside className="space-y-3">
          <Card className="surface-card rounded-xl border hairline">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold tracking-tight">Assistant output</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5 text-[12px] text-muted-foreground">
              <p>Orbit is using this board as the operational layer for deadlines, study sessions, and side-work tasks.</p>
              <Link href="/assistant?intent=show_urgent_items" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-full justify-start")}>
                Open urgent items in assistant
              </Link>
            </CardContent>
          </Card>
          <BuddyPanel insight={buddyInsight} plan={plan} />
        </aside>
      </div>
    </div>
  );
}

