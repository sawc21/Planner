import { Clock3 } from "lucide-react";

import { EmptyState } from "@/components/life-os/empty-state";
import { LifeItemCard } from "@/components/life-os/life-item-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DeadlineBucketGroup } from "@/lib/life-os/types";

export function TimelineBlock({
  group,
  focusTodayIds,
  onToggleComplete,
  onToggleFocus,
}: {
  group: DeadlineBucketGroup;
  focusTodayIds: string[];
  onToggleComplete: (itemId: string) => void;
  onToggleFocus: (itemId: string) => void;
}) {
  return (
    <Card className="surface-card border hairline">
      <CardHeader>
        <CardTitle className="font-heading text-2xl">{group.label}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {group.items.length ? (
          group.items.map((item) => (
            <LifeItemCard
              key={item.id}
              compact
              item={item}
              onToggleComplete={() => onToggleComplete(item.id)}
              onToggleFocus={() => onToggleFocus(item.id)}
              isFocused={focusTodayIds.includes(item.id)}
            />
          ))
        ) : (
          <EmptyState
            icon={Clock3}
            title={`No items in ${group.label.toLowerCase()}`}
            description="That bucket has breathing room right now, which gives the rest of the board a little more shape."
          />
        )}
      </CardContent>
    </Card>
  );
}
