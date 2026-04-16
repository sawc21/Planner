import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { WorkspacesView } from "@/components/life-os/workspaces-view";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

describe("WorkspacesView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("filters between course and project workspaces", () => {
    renderWithLifeOs(<WorkspacesView initialType="" />);

    expect(screen.getAllByText("Operating Systems").length).toBeGreaterThan(0);
    expect(screen.getByText("Orbit OS Launch Site")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /projects/i }));

    expect(screen.getByText("Orbit OS Launch Site")).toBeInTheDocument();
    expect(screen.queryAllByText("Operating Systems")).toHaveLength(0);
  });
});
