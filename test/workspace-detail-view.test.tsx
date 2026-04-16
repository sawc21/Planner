import { screen } from "@testing-library/react";
import { vi } from "vitest";

import { WorkspaceDetailView } from "@/components/life-os/workspace-detail-view";
import { REFERENCE_DATE, renderWithLifeOs } from "@/test/test-utils";

describe("WorkspaceDetailView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE_DATE);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders course mode with materials and grade summary", () => {
    renderWithLifeOs(<WorkspaceDetailView workspaceId="course-os" />);

    expect(screen.getByRole("heading", { name: /operating systems/i })).toBeInTheDocument();
    expect(screen.getByText(/grade summary/i)).toBeInTheDocument();
    expect(screen.getAllByText(/scheduler lab rubric/i).length).toBeGreaterThan(0);
  });

  it("renders project mode with milestones and progress summary", () => {
    renderWithLifeOs(<WorkspaceDetailView workspaceId="project-orbit" />);

    expect(screen.getByRole("heading", { name: /orbit os launch site/i })).toBeInTheDocument();
    expect(screen.getByText(/milestones/i)).toBeInTheDocument();
    expect(screen.getAllByText(/home dashboard polish/i).length).toBeGreaterThan(0);
  });
});
