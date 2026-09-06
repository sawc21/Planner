import { render, fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { CommandCenterView } from "@/components/life-os/command-center-view";
import { WorkspacesView } from "@/components/life-os/workspaces-view";
import { LifeOsProvider } from "@/lib/life-os/state";
import { buildSeedLifeOsData } from "@/lib/life-os/mock-data";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

vi.mock("next/navigation", () => ({
  usePathname: () => "/workspaces",
  useRouter: () => ({ push: vi.fn() }),
}));

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

  it("disables the Focused filter chip when nothing is focused", () => {
    renderWithLifeOs(<WorkspacesView initialType="" />);

    expect(screen.getByRole("button", { name: /^focused$/i })).toBeDisabled();
  });

  it("shows focus ring + Focused pill + enables filter chip after focus command", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    render(
      <LifeOsProvider initialData={data}>
        <CommandCenterView />
        <WorkspacesView initialType="" />
      </LifeOsProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /focus workspace CS 3345/i }));

    const focusedCards = document.querySelectorAll('[data-focused="true"]');
    expect(focusedCards.length).toBeGreaterThan(0);

    // Focused filter chip is now enabled
    const focusedChip = screen.getByRole("button", { name: /^focused$/i });
    expect(focusedChip).not.toBeDisabled();

    fireEvent.click(focusedChip);
    expect(document.querySelectorAll('[data-focused="true"]').length).toBe(1);
  });
});
