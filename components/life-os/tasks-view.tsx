"use client";

import { useDeferredValue, useState } from "react";
import { Search, SlidersHorizontal } from "lucide-react";

import { EmptyState } from "@/components/life-os/empty-state";
import { FilterChip } from "@/components/life-os/filter-chip";
import { LifeItemCard } from "@/components/life-os/life-item-card";
import { PageHeader } from "@/components/life-os/page-header";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getOverdueTasks,
  getTaskViews,
  getTodayTasks,
  getUpcomingTasks,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import type { TaskFilterState, TaskScope, TaskView } from "@/lib/life-os/types";
import {
  TASK_KIND_LABELS,
  TASK_KINDS,
  TASK_PRIORITY_LABELS,
  TASK_PRIORITIES,
  TASK_STATUSES,
  TASK_STATUS_LABELS,
} from "@/lib/life-os/types";

function getInitialFilters(searchParams: URLSearchParams): TaskFilterState {
  return {
    scope: (searchParams.get("scope") as TaskScope | null) ?? "all",
    workspaceId: searchParams.get("workspaceId") ?? "all",
    kind: (searchParams.get("kind") as TaskFilterState["kind"] | null) ?? "all",
    status: (searchParams.get("status") as TaskFilterState["status"] | null) ?? "all",
    priority:
      (searchParams.get("priority") as TaskFilterState["priority"] | null) ?? "all",
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
    focusTodayIds,
    toggleFocusToday,
    completeTask,
    moveTaskToTomorrow,
    startTask,
  } = useLifeOs();
  const [filters, setFilters] = useState<TaskFilterState>(() =>
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
    if (filters.workspaceId !== "all" && item.workspaceId !== filters.workspaceId) {
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
      const haystack =
        `${item.title} ${item.notes ?? ""} ${item.workspace.name} ${item.tags.join(" ")}`.toLowerCase();
      return haystack.includes(deferredQuery.toLowerCase());
    }

    return true;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Tasks"
        title="One task board, across every flow."
        description="Assignments, study sessions, bills, errands, and work tasks stay in one system, but you can still filter hard by workspace, urgency, status, and type."
      />

      <div className="surface-panel rounded-2xl border hairline p-4 sm:p-5">
        <div className="flex flex-col gap-4">
          <Tabs
            value={filters.kind}
            onValueChange={(value) =>
              setFilters((current) => ({
                ...current,
                kind: value as TaskFilterState["kind"],
              }))
            }
          >
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              {TASK_KINDS.map((kind) => (
                <TabsTrigger key={kind} value={kind}>
                  {TASK_KIND_LABELS[kind]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={filters.query}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, query: event.target.value }))
                }
                placeholder="Search titles, notes, workspaces, or tags"
                className="h-11 rounded-xl bg-card/80 pl-10"
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-3 xl:flex xl:items-center">
              <Select
                value={filters.workspaceId}
                onValueChange={(value) =>
                  setFilters((current) => ({
                    ...current,
                    workspaceId: (value ?? "all") as TaskFilterState["workspaceId"],
                  }))
                }
              >
                <SelectTrigger className="w-full rounded-xl bg-card/80 sm:w-[200px]">
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

              <Select
                value={filters.status}
                onValueChange={(value) =>
                  setFilters((current) => ({
                    ...current,
                    status: value as TaskFilterState["status"],
                  }))
                }
              >
                <SelectTrigger className="w-full rounded-xl bg-card/80 sm:w-[180px]">
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

              <Select
                value={filters.priority}
                onValueChange={(value) =>
                  setFilters((current) => ({
                    ...current,
                    priority: value as TaskFilterState["priority"],
                  }))
                }
              >
                <SelectTrigger className="w-full rounded-xl bg-card/80 sm:w-[180px]">
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
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <SlidersHorizontal className="size-4" />
              Scopes
            </span>
            {(["all", "today", "overdue", "upcoming"] as TaskScope[]).map((scope) => (
              <FilterChip
                key={scope}
                active={filters.scope === scope}
                onClick={() => setFilters((current) => ({ ...current, scope }))}
              >
                {scope === "all"
                  ? "Everything"
                  : scope === "today"
                    ? "Today"
                    : scope === "overdue"
                      ? "Overdue"
                      : "Upcoming"}
              </FilterChip>
            ))}
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Showing <span className="font-medium text-foreground">{filteredItems.length}</span> tasks
          that match the current view.
        </p>

        {filteredItems.length ? (
          filteredItems.map((item) => (
            <LifeItemCard
              key={item.id}
              compact
              item={item}
              onCompleteTask={() => completeTask(item.id)}
              onMoveTaskToTomorrow={() => moveTaskToTomorrow(item.id)}
              onStartTask={() => startTask(item.id)}
              onToggleFocus={() => toggleFocusToday(item.id)}
              isFocused={focusTodayIds.includes(item.id)}
            />
          ))
        ) : (
          <EmptyState
            icon={Search}
            title="No tasks match that combination"
            description="Try relaxing one filter or switch back to the full board to widen the view again."
          />
        )}
      </div>
    </div>
  );
}
