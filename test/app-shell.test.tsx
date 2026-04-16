import { screen } from "@testing-library/react";
import { vi } from "vitest";

import { AppShell } from "@/components/life-os/app-shell";
import { renderWithLifeOs } from "@/test/test-utils";

const usePathnameMock = vi.fn();
const useSearchParamsMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
  useSearchParams: () => useSearchParamsMock(),
}));

describe("AppShell", () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue("/tasks");
    useSearchParamsMock.mockReturnValue(new URLSearchParams());
  });

  it("shows the active navigation state and shared status strip", () => {
    renderWithLifeOs(
      <AppShell>
        <div>Child content</div>
      </AppShell>,
    );

    const tasksLink = screen.getByRole("link", { name: /tasks/i });

    expect(tasksLink.className).toContain("bg-[var(--sidebar-accent)]");
    expect(screen.getByText(/active today/i)).toBeInTheDocument();
    expect(screen.getByText("Child content")).toBeInTheDocument();
  });
});
