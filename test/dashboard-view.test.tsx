import { screen } from "@testing-library/react";
import { vi } from "vitest";

import { DashboardView } from "@/components/life-os/dashboard-view";
import { renderWithLifeOs } from "@/test/test-utils";

const usePathnameMock = vi.fn();
const useSearchParamsMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
  useSearchParams: () => useSearchParamsMock(),
}));

describe("DashboardView", () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue("/");
    useSearchParamsMock.mockReturnValue(new URLSearchParams());
  });

  it("renders the seeded widgets and recommendation card", () => {
    renderWithLifeOs(<DashboardView />);

    expect(screen.getByText(/what should i do today/i)).toBeInTheDocument();
    expect(screen.getByText("Top priorities")).toBeInTheDocument();
    expect(screen.getByText("Upcoming deadlines")).toBeInTheDocument();
    expect(screen.getByText("Quick links")).toBeInTheDocument();
  });
});
