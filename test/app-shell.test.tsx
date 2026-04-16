import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { AppShell } from "@/components/life-os/app-shell";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

const usePathnameMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
  useRouter: () => ({ push: pushMock }),
}));

describe("AppShell", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
    usePathnameMock.mockReturnValue("/workspaces");
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the Orbit navigation and system rail", () => {
    renderWithLifeOs(
      <AppShell>
        <div>Child content</div>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: /home/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /calendar/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /assignments/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /grades/i })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /assistant/i }).length).toBeGreaterThan(0);
    expect(screen.getByText(/orbit os/i)).toBeInTheDocument();
    expect(screen.getByText(/system status/i)).toBeInTheDocument();
    expect(screen.getByText(/system rail/i)).toBeInTheDocument();
    expect(screen.getByText("Child content")).toBeInTheDocument();
  });

  it("opens the quick command modal from the shell", () => {
    renderWithLifeOs(
      <AppShell>
        <div>Child content</div>
      </AppShell>,
    );

    fireEvent.click(screen.getByRole("button", { name: /quick add command/i }));

    expect(screen.getByText(/quick orbit command/i)).toBeInTheDocument();
  });
});
