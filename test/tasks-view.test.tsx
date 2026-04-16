import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { TasksView } from "@/components/life-os/tasks-view";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

describe("TasksView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("honors deep-linked filter combinations and local search", () => {
    renderWithLifeOs(<TasksView initialQueryString="scope=overdue" />);

    expect(screen.getAllByText("Schedule rent payment").length).toBeGreaterThan(0);
    expect(screen.queryByText("Prepare prototype critique talking points")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/search assignments/i), {
      target: { value: "scheduler" },
    });

    expect(screen.getByText(/no assignments match that filter/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Schedule rent payment" })).not.toBeInTheDocument();
  });
});
