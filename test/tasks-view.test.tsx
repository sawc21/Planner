import { fireEvent, screen } from "@testing-library/react";

import { TasksView } from "@/components/life-os/tasks-view";
import { renderWithLifeOs } from "@/test/test-utils";

describe("TasksView", () => {
  it("honors deep-linked filter combinations and local search", () => {
    renderWithLifeOs(<TasksView initialQueryString="scope=overdue&type=bill" />);

    expect(screen.getByText("Pay electric bill")).toBeInTheDocument();
    expect(screen.queryByText("Therapy session")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/search titles/i), {
      target: { value: "internet" },
    });

    expect(screen.getByText("Pay internet bill")).toBeInTheDocument();
    expect(screen.queryByText("Pay electric bill")).not.toBeInTheDocument();
  });
});
