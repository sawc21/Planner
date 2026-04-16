"use client";

import { createContext, useContext, useState } from "react";

import { seedLifeItems } from "@/lib/life-os/mock-data";
import type { LifeItem } from "@/lib/life-os/types";

type LifeOsContextValue = {
  items: LifeItem[];
  focusTodayIds: string[];
  toggleItemCompletion: (itemId: string) => void;
  toggleFocusToday: (itemId: string) => void;
};

const LifeOsContext = createContext<LifeOsContextValue | null>(null);

function getIncompleteStatus(item: LifeItem): LifeItem["status"] {
  if (item.type === "appointment" && item.scheduledAt) {
    return "scheduled";
  }

  if (item.type === "reminder" && item.status === "snoozed") {
    return "snoozed";
  }

  return "todo";
}

export function LifeOsProvider({
  children,
  initialItems = seedLifeItems,
}: {
  children: React.ReactNode;
  initialItems?: LifeItem[];
}) {
  const [items, setItems] = useState(initialItems);
  const [focusTodayIds, setFocusTodayIds] = useState<string[]>([]);

  const toggleItemCompletion = (itemId: string) => {
    setItems((currentItems) =>
      currentItems.map((item) => {
        if (item.id !== itemId) {
          return item;
        }

        const completeStatus = item.type === "bill" ? "paid" : "done";
        const isComplete = item.status === "done" || item.status === "paid";

        if (isComplete) {
          return {
            ...item,
            status: getIncompleteStatus(item),
            completedAt: undefined,
          };
        }

        return {
          ...item,
          status: completeStatus,
          completedAt: new Date().toISOString(),
        };
      }),
    );
  };

  const toggleFocusToday = (itemId: string) => {
    setFocusTodayIds((currentIds) =>
      currentIds.includes(itemId)
        ? currentIds.filter((currentId) => currentId !== itemId)
        : [...currentIds, itemId],
    );
  };

  return (
    <LifeOsContext.Provider
      value={{ items, focusTodayIds, toggleItemCompletion, toggleFocusToday }}
    >
      {children}
    </LifeOsContext.Provider>
  );
}

export function useLifeOs() {
  const context = useContext(LifeOsContext);

  if (!context) {
    throw new Error("useLifeOs must be used within a LifeOsProvider.");
  }

  return context;
}
