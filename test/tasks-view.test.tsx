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

    expect(screen.getByText("Schedule rent payment")).toBeInTheDocument();
    expect(screen.queryByText("Grocery reset for the week")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/search titles/i), {
      target: { value: "insurance" },
    });

    expect(screen.getByText("Upload insurance claim receipts")).toBeInTheDocument();
    expect(screen.queryByText("Schedule rent payment")).not.toBeInTheDocument();
  });
});
