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
  getOverdueItems,
  getTodayItems,
  getUpcomingDeadlines,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import type { LifeItem, TaskFilterState, TaskShortcut } from "@/lib/life-os/types";
import {
  LIFE_ITEM_PRIORITIES,
  LIFE_ITEM_STATUSES,
  LIFE_ITEM_TYPES,
  PRIORITY_LABELS,
  STATUS_LABELS,
  TYPE_LABELS,
} from "@/lib/life-os/types";

function getInitialFilters(searchParams: URLSearchParams): TaskFilterState {
  return {
    shortcut: (searchParams.get("scope") as TaskShortcut | null) ?? "all",
    type: (searchParams.get("type") as TaskFilterState["type"] | null) ?? "all",
    status: (searchParams.get("status") as TaskFilterState["status"] | null) ?? "all",
    priority:
      (searchParams.get("priority") as TaskFilterState["priority"] | null) ?? "all",
    query: searchParams.get("query") ?? "",
  };
}

function applyShortcut(items: LifeItem[], shortcut: TaskShortcut) {
  if (shortcut === "today") {
    const ids = new Set(getTodayItems(items).map((item) => item.id));
    return items.filter((item) => ids.has(item.id));
  }

  if (shortcut === "overdue") {
    const ids = new Set(getOverdueItems(items).map((item) => item.id));
    return items.filter((item) => ids.has(item.id));
  }

  if (shortcut === "upcoming") {
    const ids = new Set(getUpcomingDeadlines(items).map((item) => item.id));
    return items.filter((item) => ids.has(item.id));
  }

  return items;
}

export function TasksView({ initialQueryString = "" }: { initialQueryString?: string }) {
  const { items, focusTodayIds, toggleFocusToday, toggleItemCompletion } = useLifeOs();
  const [filters, setFilters] = useState<TaskFilterState>(() =>
    getInitialFilters(new URLSearchParams(initialQueryString)),
  );
  const deferredQuery = useDeferredValue(filters.query);

  const filteredItems = applyShortcut(items, filters.shortcut).filter((item) => {
    if (filters.type !== "all" && item.type !== filters.type) {
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
        `${item.title} ${item.notes ?? ""} ${item.category} ${item.tags.join(" ")}`.toLowerCase();
      return haystack.includes(deferredQuery.toLowerCase());
    }

    return true;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Tasks"
        title="One list, with enough shape to stay sane."
        description="Filter by type, status, urgency, or time horizon without breaking the whole board into separate silos."
      />

      <div className="surface-panel rounded-[28px] border hairline p-4 sm:p-5">
        <div className="flex flex-col gap-4">
          <Tabs
            value={filters.type}
            onValueChange={(value) =>
              setFilters((current) => ({
                ...current,
                type: value as TaskFilterState["type"],
              }))
            }
          >
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              {LIFE_ITEM_TYPES.map((type) => (
                <TabsTrigger key={type} value={type}>
                  {TYPE_LABELS[type]}
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
                placeholder="Search titles, notes, categories, or tags"
                className="h-11 rounded-2xl bg-white/70 pl-10"
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:flex xl:items-center">
              <Select
                value={filters.status}
                onValueChange={(value) =>
                  setFilters((current) => ({
                    ...current,
                    status: value as TaskFilterState["status"],
                  }))
                }
              >
                <SelectTrigger className="w-full rounded-2xl bg-white/70 sm:w-[180px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  {LIFE_ITEM_STATUSES.map((status) => (
                    <SelectItem key={status} value={status}>
                      {STATUS_LABELS[status]}
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
                <SelectTrigger className="w-full rounded-2xl bg-white/70 sm:w-[180px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All priorities</SelectItem>
                  {LIFE_ITEM_PRIORITIES.map((priority) => (
                    <SelectItem key={priority} value={priority}>
                      {PRIORITY_LABELS[priority]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <SlidersHorizontal className="size-4" />
              Shortcuts
            </span>
            {(["all", "today", "overdue", "upcoming"] as TaskShortcut[]).map((shortcut) => (
              <FilterChip
                key={shortcut}
                active={filters.shortcut === shortcut}
                onClick={() => setFilters((current) => ({ ...current, shortcut }))}
              >
                {shortcut === "all"
                  ? "Everything"
                  : shortcut === "today"
                    ? "Today"
                    : shortcut === "overdue"
                      ? "Overdue"
                      : "Upcoming"}
              </FilterChip>
            ))}
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Showing <span className="font-medium text-foreground">{filteredItems.length}</span> items
          that match the current view.
        </p>

        {filteredItems.length ? (
          filteredItems.map((item) => (
            <LifeItemCard
              key={item.id}
              compact
              item={item}
              onToggleComplete={() => toggleItemCompletion(item.id)}
              onToggleFocus={() => toggleFocusToday(item.id)}
              isFocused={focusTodayIds.includes(item.id)}
            />
          ))
        ) : (
          <EmptyState
            icon={Search}
            title="No items match that combination"
            description="Try relaxing one filter or switch back to the full list to widen the board again."
          />
        )}
      </div>
    </div>
  );
}
