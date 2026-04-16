import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { AppShell } from "@/components/life-os/app-shell";
import { getOverloadAssessment, getTodayRecommendations } from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import type { LifeOsSnapshot } from "@/lib/life-os/types";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

const usePathnameMock = vi.fn();
const useRouterMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
  useRouter: () => useRouterMock(),
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
      id: "admin-life",
      name: "Personal Admin",
      shortLabel: "ADMIN",
      kind: "admin",
      colorToken: "bg-stone-200 text-stone-900",
      icon: "wallet",
      ownerLabel: "Life flows",
      progressSummary: "Busy.",
    },
  ],
  tasks: [
    {
      id: "task-rent",
      workspaceId: "admin-life",
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
      workspaceId: "admin-life",
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
      workspaceId: "admin-life",
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
  gradebooks: [],
  progressRecords: [],
  constraintProfile: {
    weeklyHoursAvailable: 10,
    weeklyBudgetAvailable: 100,
    hoursRemainingThisWeek: 6,
    budgetRemainingThisWeek: 80,
    defaultEnergyProfile: "low",
  },
};

describe("life os state actions", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
    usePathnameMock.mockReturnValue("/tasks");
    useRouterMock.mockReturnValue({ push: vi.fn() });
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

    expect(screen.getByText(/3 overdue tasks still need relief/i)).toBeInTheDocument();
    fireEvent.click(screen.getAllByText("Move rent")[0]);
    expect(screen.getByText(/2 overdue tasks still need relief/i)).toBeInTheDocument();
  });
});
