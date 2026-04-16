import { screen } from "@testing-library/react";
import { vi } from "vitest";

import { AppShell } from "@/components/life-os/app-shell";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

const usePathnameMock = vi.fn();
const useRouterMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
  useRouter: () => useRouterMock(),
}));

describe("AppShell", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
    usePathnameMock.mockReturnValue("/workspaces");
    useRouterMock.mockReturnValue({ push: vi.fn() });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the student-and-study navigation and utility zone", () => {
    renderWithLifeOs(
      <AppShell>
        <div>Child content</div>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: /workspaces/i }).className).toContain(
      "bg-[var(--sidebar-accent)]",
    );
    expect(screen.getByText(/utility zone/i)).toBeInTheDocument();
    expect(screen.getByText(/hours left/i)).toBeInTheDocument();
    expect(screen.getByText("Child content")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /progress/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /command/i })).toBeInTheDocument();
  });
});
