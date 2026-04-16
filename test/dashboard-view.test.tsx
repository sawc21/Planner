import { screen } from "@testing-library/react";
import { vi } from "vitest";

import { DashboardView } from "@/components/life-os/dashboard-view";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

const usePathnameMock = vi.fn();
const useRouterMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
  useRouter: () => useRouterMock(),
}));

describe("DashboardView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
    usePathnameMock.mockReturnValue("/");
    useRouterMock.mockReturnValue({ push: vi.fn() });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the today board with recommendation, risk, and buddy panels", () => {
    renderWithLifeOs(<DashboardView />);

    expect(screen.getByText(/what should i do today/i)).toBeInTheDocument();
    expect(screen.getByText(/at-risk workspaces/i)).toBeInTheDocument();
    expect(screen.getByText(/today's schedule/i)).toBeInTheDocument();
    expect(screen.getByText(/constraint profile/i)).toBeInTheDocument();
    expect(screen.getByText(/suggested flow/i)).toBeInTheDocument();
  });
});
