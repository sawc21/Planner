import { INTENT_AFFECTED_SURFACES, parseCommandInput } from "@/lib/life-os/commands";

describe("command parsing", () => {
  it.each([
    ["build dashboard", "build_dashboard"],
    ["suggest widgets", "suggest_widgets"],
    ["rebalance schedule", "rebalance_schedule"],
    ["focus workspace CS 3345", "focus_workspace"],
    ["create project orbit launch site", "create_project"],
    ["create study session OS quiz review", "create_study_session"],
    ["generate weekly plan", "generate_weekly_plan"],
    ["apply weekly plan", "apply_weekly_plan"],
    ["apply plan", "apply_weekly_plan"],
    ["explain priority", "explain_priority"],
    ["show urgent items", "show_urgent_items"],
  ])("parses %s into %s", (input, intent) => {
    const result = parseCommandInput(input);

    expect("intent" in result && result.intent).toBe(intent);
  });

  it("returns the urgent navigation target", () => {
    const result = parseCommandInput("show urgent items");

    expect(result.kind).toBe("navigation");
    if (result.kind === "navigation") {
      expect(result.href).toBe("/assignments?scope=overdue");
    }
  });

  it("returns a bounded fallback for unsupported text", () => {
    const result = parseCommandInput("write me a poem");

    expect(result.kind).toBe("message");
    expect(result.message).toMatch(/i can help with/i);
  });

  it("parses clear focus into a clear-focus intent", () => {
    const result = parseCommandInput("clear focus");

    expect(result.kind).toBe("clear_focus");
  });

  it("parses remove focus as a clear-focus intent", () => {
    const result = parseCommandInput("remove focus");

    expect(result.kind).toBe("clear_focus");
  });

  it("parses rebalance schedule as a rebalance intent (not navigation)", () => {
    const result = parseCommandInput("rebalance schedule");

    expect(result.kind).toBe("rebalance");
  });

  it("exposes affected surfaces for every known intent", () => {
    expect(INTENT_AFFECTED_SURFACES.rebalance_schedule).toContain("calendar");
    expect(INTENT_AFFECTED_SURFACES.focus_workspace).toContain("workspaces");
    expect(INTENT_AFFECTED_SURFACES.generate_weekly_plan).toContain("assistant");
    expect(INTENT_AFFECTED_SURFACES.apply_weekly_plan).toContain("calendar");
    expect(INTENT_AFFECTED_SURFACES.build_dashboard).toContain("home");
  });
});
