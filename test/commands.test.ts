import { parseCommandInput } from "@/lib/life-os/commands";

describe("command parsing", () => {
  it.each([
    ["build dashboard", "build_dashboard"],
    ["suggest widgets", "suggest_widgets"],
    ["rebalance schedule", "rebalance_schedule"],
    ["focus workspace CS 3345", "focus_workspace"],
    ["create project orbit launch site", "create_project"],
    ["create study session OS quiz review", "create_study_session"],
    ["generate weekly plan", "generate_weekly_plan"],
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
});
