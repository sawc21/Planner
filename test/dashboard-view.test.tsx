import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { CommandCenterView } from "@/components/life-os/command-center-view";
import { DashboardView } from "@/components/life-os/dashboard-view";
import { LifeOsProvider } from "@/lib/life-os/state";
import { buildSeedLifeOsData } from "@/lib/life-os/mock-data";
import { render } from "@testing-library/react";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

vi.mock("next/navigation", () => ({
  usePathname: () => "/home",
  useRouter: () => ({ push: vi.fn() }),
}));

describe("DashboardView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the Orbit home widget surface", () => {
    renderWithLifeOs(<DashboardView />);

    expect(screen.getByText(/orbit is briefing the system state/i)).toBeInTheDocument();
    expect(screen.getByText(/what changed/i)).toBeInTheDocument();
    expect(screen.getByText(/no assistant receipts yet/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /open assistant/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /open assistant workbench/i })).toBeInTheDocument();
    expect(screen.getAllByText(/schedule rent payment/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/assistant route/i)).toBeInTheDocument();
  });

  it("shows active plan and focused chips after running assistant commands", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    render(
      <LifeOsProvider initialData={data}>
        <CommandCenterView />
        <DashboardView />
      </LifeOsProvider>,
    );

    // Plan chip appears after generating the weekly plan
    fireEvent.click(screen.getByRole("button", { name: /generate weekly plan/i }));
    expect(screen.getByTestId("active-plan-chip")).toBeInTheDocument();

    // Focused chip appears after focusing a workspace
    fireEvent.click(screen.getByRole("button", { name: /focus workspace CS 3345/i }));
    expect(screen.getByTestId("focused-workspace-chip")).toBeInTheDocument();

    // Activity strip renders the new events
    const strip = screen.getByTestId("activity-strip");
    expect(strip).toBeInTheDocument();
    expect(strip.textContent ?? "").toMatch(/Focused|focus/i);
  });
});
