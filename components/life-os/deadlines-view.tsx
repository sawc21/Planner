"use client";

import { useState } from "react";

import { FilterChip } from "@/components/life-os/filter-chip";
import { PageHeader } from "@/components/life-os/page-header";
import { TimelineBlock } from "@/components/life-os/timeline-block";
import { groupItemsByDeadlineBucket } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import type { DeadlineBucket } from "@/lib/life-os/types";
import { DEADLINE_BUCKET_LABELS } from "@/lib/life-os/types";

export function DeadlinesView({
  initialQueryString = "",
}: {
  initialQueryString?: string;
}) {
  const { items, focusTodayIds, toggleFocusToday, toggleItemCompletion } = useLifeOs();
  const searchParams = new URLSearchParams(initialQueryString);
  const [activeBucket, setActiveBucket] = useState<DeadlineBucket | "all">(
    (searchParams.get("bucket") as DeadlineBucket | "all" | null) ?? "all",
  );

  const groups = groupItemsByDeadlineBucket(items);
  const visibleGroups =
    activeBucket === "all" ? groups : groups.filter((group) => group.key === activeBucket);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Deadlines"
        title="See urgency without panic."
        description="Bills, appointments, and hard due dates grouped into a single timeline so you can handle the real pressure points in order."
      />

      <div className="surface-panel rounded-[28px] border hairline p-4 sm:p-5">
        <div className="flex flex-wrap gap-2">
          <FilterChip active={activeBucket === "all"} onClick={() => setActiveBucket("all")}>
            All buckets
          </FilterChip>
          {(Object.keys(DEADLINE_BUCKET_LABELS) as DeadlineBucket[]).map((bucket) => (
            <FilterChip
              key={bucket}
              active={activeBucket === bucket}
              onClick={() => setActiveBucket(bucket)}
            >
              {DEADLINE_BUCKET_LABELS[bucket]}
            </FilterChip>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        {visibleGroups.map((group) => (
          <TimelineBlock
            key={group.key}
            group={group}
            focusTodayIds={focusTodayIds}
            onToggleComplete={toggleItemCompletion}
            onToggleFocus={toggleFocusToday}
          />
        ))}
      </div>
    </div>
  );
}
