import { render, fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { CalendarView } from "@/components/life-os/calendar-view";
import { CommandCenterView } from "@/components/life-os/command-center-view";
import { LifeOsProvider } from "@/lib/life-os/state";
import { buildSeedLifeOsData } from "@/lib/life-os/mock-data";
import { REFERENCE_DATE } from "@/test/test-utils";

vi.mock("next/navigation", () => ({
  usePathname: () => "/calendar",
  useRouter: () => ({ push: vi.fn() }),
}));

describe("CalendarView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the pending schedule panel even with no suggestions yet", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    render(
      <LifeOsProvider initialData={data}>
        <CalendarView />
      </LifeOsProvider>,
    );

    expect(screen.getByTestId("pending-schedule-panel")).toBeInTheDocument();
    expect(screen.getByText(/no schedule changes pending/i)).toBeInTheDocument();
  });

  it("renders plan markers on day buttons after generate weekly plan", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    render(
      <LifeOsProvider initialData={data}>
        <CommandCenterView />
        <CalendarView />
      </LifeOsProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /generate weekly plan/i }));

    // At least one plan marker should be rendered on a day cell
    const markers = screen.queryAllByText(/plan step/i);
    expect(markers.length).toBeGreaterThan(0);
  });
});
