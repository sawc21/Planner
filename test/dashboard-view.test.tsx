import { screen } from "@testing-library/react";
import { vi } from "vitest";

import { DashboardView } from "@/components/life-os/dashboard-view";
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
});
