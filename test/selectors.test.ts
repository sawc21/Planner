import { buildCalmLifeOsData, buildSeedLifeOsData } from "@/lib/life-os/mock-data";
import {
  getAtRiskWorkspaces,
  getConstraintAwarePlan,
  getOverloadAssessment,
  getProgressCards,
  getTodayRecommendations,
} from "@/lib/life-os/selectors";

const REFERENCE_DATE = new Date("2026-04-16T09:00:00-05:00");

describe("life os selectors", () => {
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

  it("exposes student, study-track, and life/admin workspaces in the seeded data", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const kinds = new Set(data.workspaces.map((workspace) => workspace.kind));

    expect(kinds.has("course")).toBe(true);
    expect(kinds.has("study_track")).toBe(true);
    expect(kinds.has("admin")).toBe(true);
    expect(kinds.has("personal")).toBe(true);
    expect(kinds.has("work")).toBe(true);
  });

  it("builds at-risk workspaces and a constraint-aware plan from the shared core", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const atRisk = getAtRiskWorkspaces(data, REFERENCE_DATE);
    const plan = getConstraintAwarePlan(data, undefined, REFERENCE_DATE);

    expect(atRisk[0]?.workspace.id).toBe("course-os");
    expect(plan.steps.length).toBeGreaterThan(0);
    expect(plan.summary).toMatch(/hours/i);
  });

  it("builds separate progress cards for courses and study tracks", () => {
    const data = buildSeedLifeOsData(REFERENCE_DATE);
    const cards = getProgressCards(data);

    expect(cards.courseCards.length).toBeGreaterThan(0);
    expect(cards.trackCards.length).toBeGreaterThan(0);
    expect(cards.lifeCards.length).toBeGreaterThan(0);
  });
});
