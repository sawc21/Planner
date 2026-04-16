import { buildCalmLifeOsData, buildSeedLifeOsData } from "@/lib/life-os/mock-data";
import {
  getAgendaGroups,
  getAtRiskWorkspaces,
  getConstraintAwarePlan,
  getGradeWhatIfCards,
  getHomeWidgetData,
  getOverloadAssessment,
  getSemesterGpaSnapshot,
  getTodayRecommendations,
  getUrgentDeadlines,
} from "@/lib/life-os/selectors";

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
});
