import { parseCommandInput } from "@/lib/life-os/commands";

describe("command parsing", () => {
  it.each([
    ["add task finish OS lab write-up", "add_task"],
    ["add event advisor check-in", "add_event"],
    ["add material interview notes", "add_material"],
    ["create workspace spanish writing sprint", "create_workspace"],
    ["what should i do today", "what_should_i_do_today"],
    ["build study flow", "build_study_flow"],
    ["show at-risk workspaces", "show_at_risk_workspaces"],
    ["rebalance week", "rebalance_week"],
    ["show urgent items", "show_urgent_items"],
  ])("parses %s into %s", (input, intent) => {
    const result = parseCommandInput(input);

    expect("intent" in result && result.intent).toBe(intent);
  });

  it("returns the urgent navigation target", () => {
    const result = parseCommandInput("show urgent items");

    expect(result.kind).toBe("navigation");
    if (result.kind === "navigation") {
      expect(result.href).toBe("/tasks?priority=high");
    }
  });

  it("returns a bounded fallback for unsupported text", () => {
    const result = parseCommandInput("write me a poem");

    expect(result.kind).toBe("message");
    expect(result.message).toMatch(/i can help with/i);
  });
});
