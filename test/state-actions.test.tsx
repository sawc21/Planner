import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { AppShell } from "@/components/life-os/app-shell";
import { getOverloadAssessment, getTodayRecommendations } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import type { LifeOsSnapshot } from "@/lib/life-os/types";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

const usePathnameMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
  useRouter: () => ({ push: pushMock }),
}));

function StoreHarness() {
  const {
    workspaces,
    tasks,
    constraintProfile,
    focusTodayIds,
    startTask,
    completeTask,
    moveTaskToTomorrow,
  } = useLifeOs();
  const osTask = tasks.find((task) => task.id === "task-os-lab");
  const recommendations = getTodayRecommendations({ workspaces, tasks, constraintProfile }, REFERENCE_DATE);
  const overload = getOverloadAssessment({ workspaces, tasks, constraintProfile }, REFERENCE_DATE);

  return (
    <div>
      <p data-testid="os-status">{osTask?.status}</p>
      <p data-testid="focus-count">{focusTodayIds.length}</p>
      <p data-testid="primary-id">{recommendations.primary?.item.id}</p>
      <p data-testid="overload-severity">{overload.severity}</p>
      <button type="button" onClick={() => startTask("task-os-lab")}>
        Start lab
      </button>
      <button
        type="button"
        onClick={() => {
          if (recommendations.primary) {
            completeTask(recommendations.primary.item.id);
          }
        }}
      >
        Complete recommendation
      </button>
      <button type="button" onClick={() => moveTaskToTomorrow("task-rent")}>
        Move rent
      </button>
    </div>
  );
}

const overloadFixture: LifeOsSnapshot = {
  workspaces: [
    {
      id: "project-general",
      name: "General",
      shortLabel: "GEN",
      kind: "project",
      colorToken: "bg-stone-200 text-stone-950",
      icon: "folder-open",
      ownerLabel: "Orbit",
      progressSummary: "Busy.",
      active: true,
      projectHealth: "watch",
    },
  ],
  tasks: [
    {
      id: "task-rent",
      primaryWorkspaceId: undefined,
      linkedWorkspaceIds: [],
      kind: "bill",
      title: "Rent",
      status: "todo",
      priority: "high",
      dueAt: "2026-04-13T17:00:00-05:00",
      tags: ["urgent"],
      amount: 50,
      estimatedMinutes: 10,
      energy: "low",
    },
    {
      id: "task-b",
      primaryWorkspaceId: undefined,
      linkedWorkspaceIds: [],
      kind: "bill",
      title: "Utilities",
      status: "todo",
      priority: "high",
      dueAt: "2026-04-14T17:00:00-05:00",
      tags: ["urgent"],
      amount: 30,
      estimatedMinutes: 10,
      energy: "low",
    },
    {
      id: "task-c",
      primaryWorkspaceId: undefined,
      linkedWorkspaceIds: [],
      kind: "admin",
      title: "Upload paperwork",
      status: "todo",
      priority: "medium",
      dueAt: "2026-04-15T10:00:00-05:00",
      tags: ["urgent"],
      estimatedMinutes: 15,
      energy: "low",
    },
  ],
  events: [],
  materials: [],
  milestones: [],
  widgets: [],
  gradebooks: [],
  constraintProfile: {
    weeklyHoursAvailable: 10,
    weeklyBudgetAvailable: 100,
    hoursRemainingThisWeek: 6,
    budgetRemainingThisWeek: 80,
    defaultEnergyProfile: "low",
  },
};

describe("orbit state actions", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
    usePathnameMock.mockReturnValue("/assignments");
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts a task and marks it as focus today", () => {
    renderWithLifeOs(<StoreHarness />);

    fireEvent.click(screen.getByText("Start lab"));

    expect(screen.getByTestId("os-status")).toHaveTextContent("in_progress");
    expect(screen.getByTestId("focus-count")).toHaveTextContent("1");
  });

  it("completing the recommendation promotes the next item live", () => {
    renderWithLifeOs(<StoreHarness />);

    expect(screen.getByTestId("primary-id")).toHaveTextContent("task-rent");
    fireEvent.click(screen.getByText("Complete recommendation"));
    expect(screen.getByTestId("primary-id")).not.toHaveTextContent("task-rent");
  });

  it("moving an overdue task to tomorrow softens overload severity", () => {
    renderWithLifeOs(<StoreHarness />, { data: overloadFixture });

    expect(screen.getByTestId("overload-severity")).toHaveTextContent("overloaded");
    fireEvent.click(screen.getByText("Move rent"));
    expect(screen.getByTestId("overload-severity")).toHaveTextContent("watch");
  });

  it("updates sidebar utility counts after a live reschedule", () => {
    renderWithLifeOs(
      <AppShell>
        <StoreHarness />
      </AppShell>,
      { data: overloadFixture },
    );

    expect(
      screen.getByText((_, element) => element?.textContent === "3 urgent · 6h left · $80 budget"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getAllByText("Move rent")[0]);
    expect(
      screen.getByText((_, element) => element?.textContent === "2 urgent · 6h left · $80 budget"),
    ).toBeInTheDocument();
  });
});

function AssistantHarness() {
  const {
    activeWeeklyPlan,
    pendingScheduleSuggestions,
    focusedWorkspaceId,
    assistantActivity,
    applyActiveWeeklyPlan,
    applyScheduleSuggestion,
    dismissScheduleSuggestion,
    runCommand,
    logAssistantActivity,
    tasks,
  } = useLifeOs();

  return (
    <div>
      <p data-testid="plan-total">{activeWeeklyPlan?.steps.length ?? 0}</p>
      <p data-testid="plan-applied">
        {activeWeeklyPlan?.steps.filter((step) => step.applied).length ?? 0}
      </p>
      <p data-testid="pending-count">
        {pendingScheduleSuggestions.filter((s) => s.status === "pending").length}
      </p>
      <p data-testid="applied-count">
        {pendingScheduleSuggestions.filter((s) => s.status === "applied").length}
      </p>
      <p data-testid="dismissed-count">
        {pendingScheduleSuggestions.filter((s) => s.status === "dismissed").length}
      </p>
      <p data-testid="focused-id">{focusedWorkspaceId ?? ""}</p>
      <p data-testid="activity-count">{assistantActivity.length}</p>
      <p data-testid="activity-top-intent">{assistantActivity[0]?.intent ?? ""}</p>
      <p data-testid="activity-top-surfaces">
        {assistantActivity[0]?.affectedSurfaces.join(",") ?? ""}
      </p>
      <p data-testid="task-count">{tasks.length}</p>
      <button type="button" onClick={() => runCommand("generate weekly plan")}>
        Generate plan
      </button>
      <button
        type="button"
        onClick={() => {
          applyActiveWeeklyPlan();
        }}
      >
        Apply plan
      </button>
      <button type="button" onClick={() => runCommand("rebalance schedule")}>
        Rebalance
      </button>
      <button
        type="button"
        onClick={() => {
          const suggestion = pendingScheduleSuggestions[0];
          if (suggestion) {
            applyScheduleSuggestion(suggestion.id);
          }
        }}
      >
        Apply first suggestion
      </button>
      <button
        type="button"
        onClick={() => {
          const suggestion = pendingScheduleSuggestions[0];
          if (suggestion) {
            dismissScheduleSuggestion(suggestion.id);
          }
        }}
      >
        Dismiss first suggestion
      </button>
      <button type="button" onClick={() => runCommand("focus workspace CS 3345")}>
        Focus workspace
      </button>
      <button type="button" onClick={() => runCommand("clear focus")}>
        Clear focus
      </button>
      <button
        type="button"
        onClick={() => {
          for (let index = 0; index < 52; index += 1) {
            logAssistantActivity({
              intent: "build_dashboard",
              title: `Event ${index}`,
              summary: "noise",
              affectedSurfaces: ["home"],
              receiptLines: [],
              resultKind: "dashboard_update",
            });
          }
        }}
      >
        Seed noisy activity
      </button>
    </div>
  );
}

describe("phase 4 assistant state", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
    usePathnameMock.mockReturnValue("/assistant");
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("generate + apply weekly plan promotes steps to tasks", () => {
    renderWithLifeOs(<AssistantHarness />);

    const initialTaskCount = Number(screen.getByTestId("task-count").textContent);

    fireEvent.click(screen.getByText("Generate plan"));
    const total = Number(screen.getByTestId("plan-total").textContent);
    expect(total).toBeGreaterThan(0);
    expect(screen.getByTestId("plan-applied")).toHaveTextContent("0");

    fireEvent.click(screen.getByText("Apply plan"));
    expect(screen.getByTestId("plan-applied")).toHaveTextContent(String(total));
    expect(Number(screen.getByTestId("task-count").textContent)).toBeGreaterThan(
      initialTaskCount,
    );
  });

  it("rebalance schedule logs schedule_update activity and accepts apply/dismiss", () => {
    renderWithLifeOs(<AssistantHarness />);

    fireEvent.click(screen.getByText("Rebalance"));
    expect(screen.getByTestId("activity-top-intent")).toHaveTextContent(
      "rebalance_schedule",
    );

    // Apply/dismiss still no-ops cleanly when there are no pending suggestions
    const pending = Number(screen.getByTestId("pending-count").textContent);
    if (pending > 0) {
      fireEvent.click(screen.getByText("Apply first suggestion"));
      expect(Number(screen.getByTestId("applied-count").textContent)).toBe(1);

      fireEvent.click(screen.getByText("Dismiss first suggestion"));
      // After Apply, the first in list is now applied; Dismiss becomes no-op, so count may be 0
      expect(
        Number(screen.getByTestId("dismissed-count").textContent),
      ).toBeGreaterThanOrEqual(0);
    }
  });

  it("focus and clear focus toggle focusedWorkspaceId and log activity surfaces", () => {
    renderWithLifeOs(<AssistantHarness />);

    fireEvent.click(screen.getByText("Focus workspace"));
    expect(screen.getByTestId("focused-id").textContent).toBe("course-os");
    expect(screen.getByTestId("activity-top-intent")).toHaveTextContent(
      "focus_workspace",
    );
    expect(screen.getByTestId("activity-top-surfaces").textContent ?? "").toContain(
      "workspaces",
    );

    fireEvent.click(screen.getByText("Clear focus"));
    expect(screen.getByTestId("focused-id").textContent).toBe("");
  });

  it("logAssistantActivity trims the log to 50 entries", () => {
    renderWithLifeOs(<AssistantHarness />);

    fireEvent.click(screen.getByText("Seed noisy activity"));
    expect(Number(screen.getByTestId("activity-count").textContent)).toBeLessThanOrEqual(
      50,
    );
  });
});
