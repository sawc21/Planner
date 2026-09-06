import { render, fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { CommandResultView } from "@/components/life-os/command-result-view";
import type {
  ActiveWeeklyPlan,
  CommandResult,
  ScheduleSuggestion,
} from "@/lib/life-os/types";

vi.mock("next/navigation", () => ({
  usePathname: () => "/assistant",
  useRouter: () => ({ push: vi.fn() }),
}));

const BASE_RECEIPT = {
  id: "receipt-1",
  title: "Receipt",
  category: "update",
  lines: ["line one"],
  generatedAt: "2026-04-16T10:00:00-05:00",
};

describe("CommandResultView", () => {
  it("renders PlanUpdateCard for plan_update results and fires onPlanApply", () => {
    const plan: ActiveWeeklyPlan = {
      id: "plan-1",
      generatedAt: "2026-04-16T10:00:00-05:00",
      horizonDays: 7,
      title: "Constraint-aware weekly plan",
      summary: "Place five focused sessions this week.",
      steps: [
        {
          id: "step-1",
          title: "Review OS notes",
          minutes: 45,
          reason: "Heaviest exam exposure",
          workspaceId: "course-os",
          scheduledFor: "2026-04-17T15:00:00-05:00",
          applied: false,
        },
      ],
    };

    const result: CommandResult = {
      intent: "generate_weekly_plan",
      kind: "plan_update",
      message: "Weekly plan ready",
      plan,
      appliedCount: 0,
      receipt: { ...BASE_RECEIPT, title: "Weekly plan ready" },
    };

    const onPlanApply = vi.fn();
    render(<CommandResultView result={result} onPlanApply={onPlanApply} />);

    expect(screen.getByText(/constraint-aware weekly plan/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /apply to this week/i }));
    expect(onPlanApply).toHaveBeenCalledTimes(1);
  });

  it("renders ScheduleUpdateCard and fires per-row Apply/Dismiss", () => {
    const suggestions: ScheduleSuggestion[] = [
      {
        id: "sug-1",
        generatedAt: "2026-04-16T10:00:00-05:00",
        kind: "shift",
        taskId: "task-x",
        title: "Shift PHYS set to Fri",
        reason: "Thursday is heavy; Friday has open room.",
        toAt: "2026-04-17T15:00:00-05:00",
        affectedDays: ["2026-04-16", "2026-04-17"],
        status: "pending",
      },
    ];
    const result: CommandResult = {
      intent: "rebalance_schedule",
      kind: "schedule_update",
      message: "Rebalance suggestions",
      suggestions,
      receipt: { ...BASE_RECEIPT, title: "Rebalance ready" },
    };

    const onSuggestionApply = vi.fn();
    const onSuggestionDismiss = vi.fn();
    render(
      <CommandResultView
        result={result}
        onSuggestionApply={onSuggestionApply}
        onSuggestionDismiss={onSuggestionDismiss}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^apply$/i }));
    expect(onSuggestionApply).toHaveBeenCalledWith("sug-1");

    fireEvent.click(screen.getByRole("button", { name: /^dismiss$/i }));
    expect(onSuggestionDismiss).toHaveBeenCalledWith("sug-1");
  });

  it("renders WorkspaceFocusCard with Clear focus button when a workspace is focused", () => {
    const result: CommandResult = {
      intent: "focus_workspace",
      kind: "workspace_focus",
      message: "Focused CS 3345",
      workspaceId: "course-os",
      affectedSurfaces: ["workspaces", "home"],
      receipt: { ...BASE_RECEIPT, title: "Focus set" },
    };

    const onClearFocus = vi.fn();
    render(<CommandResultView result={result} onClearFocus={onClearFocus} />);

    expect(screen.getByText(/focused cs 3345/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /clear focus/i }));
    expect(onClearFocus).toHaveBeenCalledTimes(1);
  });

  it("renders NavigationCard with a deep link", () => {
    const result: CommandResult = {
      intent: "show_urgent_items",
      kind: "navigation",
      message: "Opening urgent items",
      href: "/assignments?scope=overdue",
    };

    render(<CommandResultView result={result} />);

    expect(screen.getByRole("link", { name: /open/i })).toHaveAttribute(
      "href",
      "/assignments?scope=overdue",
    );
  });

  it("renders MessageCard for fallback messages", () => {
    const result: CommandResult = {
      kind: "message",
      message: "I cannot help with that yet.",
    };

    render(<CommandResultView result={result} />);

    expect(screen.getByText(/i cannot help with that yet/i)).toBeInTheDocument();
  });
});
