import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { CommandCenterView } from "@/components/life-os/command-center-view";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

vi.mock("next/navigation", () => ({
  usePathname: () => "/assistant",
  useRouter: () => ({ push: vi.fn() }),
}));

describe("CommandCenterView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders structured assistant command results", () => {
    renderWithLifeOs(<CommandCenterView />);

    fireEvent.click(screen.getByRole("button", { name: /generate weekly plan/i }));

    expect(screen.getByText(/dedicated assistant workbench/i)).toBeInTheDocument();
    expect(screen.getByText(/structured result stack/i)).toBeInTheDocument();
    expect(screen.getAllByText(/weekly plan ready/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/action receipts/i)).toBeInTheDocument();
  });
});
