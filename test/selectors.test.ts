import { buildCalmLifeOsData, buildSeedLifeOsData } from "@/lib/life-os/mock-data";
import {
  buildActiveWeeklyPlan,
  computeScheduleRebalance,
  getAgendaGroups,
  getAtRiskWorkspaces,
  getConstraintAwarePlan,
  getFocusedWorkspaceStatus,
  getGradeWhatIfCards,
  getHomeWidgetData,
  getOverloadAssessment,
  getRecentAssistantActivity,
  getScheduleRebalanceSummary,
  getSemesterGpaSnapshot,
  getTodayRecommendations,
  getUrgentDeadlines,
  getWeeklyPlanSummary,
} from "@/lib/life-os/selectors";
import type {
  AssistantActivityEvent,
  ScheduleSuggestion,
} from "@/lib/life-os/types";

const REFERENCE_DATE = new Date("2026-04-16T09:00:00-05:00");

describe("orbit selectors", () => {
  it("flags overload for the seeded fixture and keeps the calm fixture below threshold", () => {
    const busyData = buildSeedLifeOsData(REFERENCE_DATE);
    const calmData = buildCalmLifeOsData(REFERENCE_DATE);

    expect(getOverloadAssessment(busyData, REFERENCE_DATE).severity).toBe("overloaded");
    expect(getOverloadAssessment(calmData, REFERENCE_DATE).severity).toBe("calm");
  });

  it("returns a deterministic recommendation with explanation and signals", () => {
    const recommendations = getTodayRecommendations(buildSeedLifeOsData(REFERENCE_DATE), REFERENCE_DATE);

    expect(recommendations.primary?.item.id).toBe("task-rent");
    expect(recommendations.primary?.scoreBreakdown.length).toBeGreaterThan(0);
    expect(recommendations.primary?.explanation).toMatch(/chosen because/i);
    expect(recommendations.secondary).toHaveLength(2);
  });

  it("exposes courses and projects in the seeded data", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const kinds = new Set(data.workspaces.map((workspace) => workspace.kind));

    expect(kinds.has("course")).toBe(true);
    expect(kinds.has("project")).toBe(true);
    expect(data.workspaces.filter((workspace) => workspace.kind === "course")).toHaveLength(4);
    expect(data.workspaces.filter((workspace) => workspace.kind === "project")).toHaveLength(3);
  });

  it("builds dashboard widgets, urgent deadlines, and agenda load bars", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const widgets = getHomeWidgetData(data, REFERENCE_DATE);
    const urgent = getUrgentDeadlines(data, REFERENCE_DATE);
    const agenda = getAgendaGroups(data, REFERENCE_DATE);

    expect(widgets.length).toBeGreaterThan(4);
    expect(urgent[0]?.id).toBe("task-rent");
    expect(agenda[0]?.loadPercent).toBeGreaterThanOrEqual(0);
    expect(agenda[0]?.openWindows.length).toBeGreaterThan(0);
  });

  it("builds at-risk workspaces and a constraint-aware plan from the shared core", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const atRisk = getAtRiskWorkspaces(data, REFERENCE_DATE);
    const plan = getConstraintAwarePlan(data, undefined, REFERENCE_DATE);

    expect(atRisk[0]?.workspace.id).toBe("course-os");
    expect(plan.steps.length).toBeGreaterThan(0);
    expect(plan.summary).toMatch(/hours/i);
  });

  it("builds GPA and what-if cards for course workspaces", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const semester = getSemesterGpaSnapshot(data);
    const cards = getGradeWhatIfCards(data);

    expect(semester.gpa).toBeGreaterThan(0);
    expect(cards.length).toBeGreaterThan(0);
    expect(cards[0]?.neededScore).toBeGreaterThan(0);
  });

  it("buildActiveWeeklyPlan produces placed steps for the seed data", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const plan = buildActiveWeeklyPlan(data, REFERENCE_DATE);

    expect(plan.steps.length).toBeGreaterThan(0);
    plan.steps.forEach((step) => {
      expect(step.applied).toBe(false);
      expect(step.scheduledFor).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    });
  });

  it("computeScheduleRebalance is deterministic across calls", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const first = computeScheduleRebalance(data, REFERENCE_DATE);
    const second = computeScheduleRebalance(data, REFERENCE_DATE);

    expect(first.length).toBeLessThanOrEqual(5);
    expect(first.map((s) => s.title)).toEqual(second.map((s) => s.title));
  });

  it("getWeeklyPlanSummary totals minutes and counts applied steps", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const plan = buildActiveWeeklyPlan(data, REFERENCE_DATE);
    const summary = getWeeklyPlanSummary(plan);

    expect(summary).not.toBeNull();
    expect(summary!.totalSteps).toBe(plan.steps.length);
    expect(summary!.appliedCount).toBe(0);
    expect(summary!.totalMinutes).toBe(
      plan.steps.reduce((sum, step) => sum + step.minutes, 0),
    );
  });

  it("getWeeklyPlanSummary returns null when no active plan", () => {
    expect(getWeeklyPlanSummary(null)).toBeNull();
  });

  it("getScheduleRebalanceSummary counts pending vs applied", () => {
    const base: ScheduleSuggestion = {
      id: "s-1",
      generatedAt: REFERENCE_DATE.toISOString(),
      kind: "shift",
      title: "Move PHYS set",
      reason: "Thursday is heavy",
      toAt: "2026-04-17T15:00:00-05:00",
      affectedDays: ["2026-04-17"],
      status: "pending",
    };
    const summary = getScheduleRebalanceSummary([
      { ...base, id: "s-1", status: "pending" },
      { ...base, id: "s-2", status: "applied", appliedAt: "now" },
      { ...base, id: "s-3", status: "dismissed" },
    ]);

    expect(summary.pendingCount).toBe(1);
    expect(summary.appliedCount).toBe(1);
    expect(summary.affectedDays).toContain("2026-04-17");
  });

  it("getFocusedWorkspaceStatus returns the focused workspace metadata", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const courseWorkspace = data.workspaces.find((w) => w.kind === "course");

    expect(courseWorkspace).toBeDefined();
    const status = getFocusedWorkspaceStatus(
      courseWorkspace!.id,
      data.workspaces,
      data.tasks,
    );

    expect(status).not.toBeNull();
    expect(status!.workspace?.id).toBe(courseWorkspace!.id);
    expect(status!.surfaces).toContain("workspaces");
  });

  it("getFocusedWorkspaceStatus returns null without a focus", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    expect(getFocusedWorkspaceStatus(null, data.workspaces, data.tasks)).toBeNull();
  });

  it("getRecentAssistantActivity truncates to the limit", () => {
    const events: AssistantActivityEvent[] = Array.from({ length: 20 }, (_, index) => ({
      id: `event-${index}`,
      at: new Date(REFERENCE_DATE.getTime() - index * 1000).toISOString(),
      intent: "build_dashboard",
      title: `Event ${index}`,
      summary: "summary",
      affectedSurfaces: ["home"],
      receiptLines: [],
      read: false,
      resultKind: "dashboard_update",
    }));

    expect(getRecentAssistantActivity(events, 5)).toHaveLength(5);
    expect(getRecentAssistantActivity(events).length).toBeLessThanOrEqual(8);
  });
});
