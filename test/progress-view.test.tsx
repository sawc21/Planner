import { screen } from "@testing-library/react";
import { vi } from "vitest";

import { ProgressView } from "@/components/life-os/progress-view";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

describe("ProgressView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the GPA snapshot and what-if guidance", () => {
    renderWithLifeOs(<ProgressView />);

    expect(screen.getByText(/semester gpa snapshot/i)).toBeInTheDocument();
    expect(screen.getByText(/what-if panel/i)).toBeInTheDocument();
    expect(screen.getAllByText(/orbit estimates you need about/i).length).toBeGreaterThan(0);
  });
});
