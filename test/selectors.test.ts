import { buildCalmFixture, buildSeedLifeItems } from "@/lib/life-os/mock-data";
import {
  getOverloadAssessment,
  getTodayRecommendations,
  groupItemsByDeadlineBucket,
} from "@/lib/life-os/selectors";

const REFERENCE_DATE = new Date("2026-04-16T09:00:00-05:00");

describe("life os selectors", () => {
  it("flags overload for the seeded fixture and keeps the calm fixture below threshold", () => {
    const busyAssessment = getOverloadAssessment(buildSeedLifeItems(REFERENCE_DATE), REFERENCE_DATE);
    const calmAssessment = getOverloadAssessment(buildCalmFixture(REFERENCE_DATE), REFERENCE_DATE);

    expect(busyAssessment.isOverloaded).toBe(true);
    expect(calmAssessment.isOverloaded).toBe(false);
  });

  it("returns a deterministic top recommendation", () => {
    const recommendations = getTodayRecommendations(buildSeedLifeItems(REFERENCE_DATE), REFERENCE_DATE);

    expect(recommendations.primary?.item.id).toBe("property-tax");
    expect(recommendations.secondary).toHaveLength(2);
  });

  it("groups deadlines into the expected urgency buckets", () => {
    const groups = groupItemsByDeadlineBucket(buildSeedLifeItems(REFERENCE_DATE), REFERENCE_DATE);

    expect(groups.find((group) => group.key === "overdue")?.items.length).toBeGreaterThan(0);
    expect(
      groups.find((group) => group.key === "next3Days")?.items.some((item) => item.id === "budget-review"),
    ).toBe(true);
  });
});
