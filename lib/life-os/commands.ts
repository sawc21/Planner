import type {
  AddEventInput,
  AddMaterialInput,
  AddTaskInput,
  CommandResult,
  CreateWorkspaceInput,
  StudyPlan,
  TodayRecommendation,
} from "@/lib/life-os/types";

type ParsedCommand =
  | {
      intent: "add_task";
      kind: "add_task";
      input: AddTaskInput;
      message: string;
    }
  | {
      intent: "add_event";
      kind: "add_event";
      input: AddEventInput;
      message: string;
    }
  | {
      intent: "add_material";
      kind: "add_material";
      input: AddMaterialInput;
      message: string;
    }
  | {
      intent: "create_workspace";
      kind: "create_workspace";
      input: CreateWorkspaceInput;
      message: string;
    }
  | {
      intent: "what_should_i_do_today";
      kind: "recommendation";
      message: string;
    }
  | {
      intent: "build_study_flow";
      kind: "plan";
      message: string;
    }
  | {
      intent: "show_at_risk_workspaces" | "rebalance_week" | "show_urgent_items";
      kind: "navigation";
      href: string;
      message: string;
    }
  | {
      kind: "message";
      message: string;
    };

const ADD_TASK_PATTERNS: Array<{
  pattern: RegExp;
  kind: AddTaskInput["kind"];
}> = [
  { pattern: /^add bill\s+(.+)$/i, kind: "bill" },
  { pattern: /^add errand\s+(.+)$/i, kind: "errand" },
  { pattern: /^add task\s+(.+)$/i, kind: "assignment" },
  { pattern: /^add study session\s+(.+)$/i, kind: "study_session" },
];

export function parseCommandInput(input: string): ParsedCommand {
  const trimmed = input.trim();

  if (!trimmed) {
    return {
      kind: "message",
      message:
        "Try a literal command like add task finish OS lab, add material interview guide, or build study flow.",
    };
  }

  for (const command of ADD_TASK_PATTERNS) {
    const match = trimmed.match(command.pattern);

    if (!match?.[1]?.trim()) {
      continue;
    }

    return {
      intent: "add_task",
      kind: "add_task",
      message: `Added ${command.kind === "bill" ? "bill" : "task"}: ${match[1].trim()}.`,
      input: {
        title: match[1].trim(),
        kind: command.kind,
      },
    };
  }

  const addEventMatch = trimmed.match(/^add (event|class)\s+(.+)$/i);
  if (addEventMatch?.[2]?.trim()) {
    return {
      intent: "add_event",
      kind: "add_event",
      message: `Added event: ${addEventMatch[2].trim()}.`,
      input: {
        title: addEventMatch[2].trim(),
        kind: "session",
      },
    };
  }

  const addMaterialMatch = trimmed.match(/^add material\s+(.+)$/i);
  if (addMaterialMatch?.[1]?.trim()) {
    return {
      intent: "add_material",
      kind: "add_material",
      message: `Added material: ${addMaterialMatch[1].trim()}.`,
      input: {
        title: addMaterialMatch[1].trim(),
        kind: "notes",
      },
    };
  }

  const createWorkspaceMatch = trimmed.match(/^create workspace\s+(.+)$/i);
  if (createWorkspaceMatch?.[1]?.trim()) {
    return {
      intent: "create_workspace",
      kind: "create_workspace",
      message: `Created workspace: ${createWorkspaceMatch[1].trim()}.`,
      input: {
        name: createWorkspaceMatch[1].trim(),
      },
    };
  }

  if (/^(what should i do today|recommend|show recommendation)$/i.test(trimmed)) {
    return {
      intent: "what_should_i_do_today",
      kind: "recommendation",
      message: "Here is the clearest next move right now.",
    };
  }

  if (/^(build study flow|make plan|create plan)$/i.test(trimmed)) {
    return {
      intent: "build_study_flow",
      kind: "plan",
      message: "Building a constraint-aware study flow now.",
    };
  }

  if (/^(show at-risk workspaces|at-risk workspaces)$/i.test(trimmed)) {
    return {
      intent: "show_at_risk_workspaces",
      kind: "navigation",
      href: "/workspaces?view=at-risk",
      message: "Opening the workspaces most likely to slip next.",
    };
  }

  if (/^(rebalance week|rebalance the week)$/i.test(trimmed)) {
    return {
      intent: "rebalance_week",
      kind: "navigation",
      href: "/agenda?view=rebalance",
      message: "Opening the agenda so you can rebalance the week.",
    };
  }

  if (/^(show urgent items|urgent items)$/i.test(trimmed)) {
    return {
      intent: "show_urgent_items",
      kind: "navigation",
      href: "/tasks?priority=high",
      message: "Opening the urgent task view for high and critical work.",
    };
  }

  return {
    kind: "message",
    message:
      "I can help with add task, add event, add material, create workspace, what should I do today, build study flow, show at-risk workspaces, rebalance week, or show urgent items.",
  };
}

export function buildRecommendationCommandResult(
  recommendation?: TodayRecommendation,
): CommandResult {
  return {
    intent: "what_should_i_do_today",
    kind: "recommendation",
    message: recommendation
      ? `Start with ${recommendation.item.title}. ${recommendation.explanation}`
      : "Nothing urgent is pressing right now.",
    recommendation,
  };
}

export function buildPlanCommandResult(plan: StudyPlan): CommandResult {
  return {
    intent: "build_study_flow",
    kind: "plan",
    message: plan.summary,
    plan,
  };
}
