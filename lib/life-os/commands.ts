import type {
  AddEventInput,
  AddMaterialInput,
  AddTaskInput,
  AssistantReceipt,
  CommandIntent,
  CommandResult,
  CreateWorkspaceInput,
  DashboardWidget,
  StudyPlan,
  TodayRecommendation,
} from "@/lib/life-os/types";

type ParsedCommand =
  | {
      intent: "add_task" | "create_study_session";
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
      intent: "create_project";
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
      intent: "generate_weekly_plan";
      kind: "plan";
      message: string;
    }
  | {
      intent: "build_dashboard" | "suggest_widgets";
      kind: "dashboard";
      message: string;
    }
  | {
      intent: "rebalance_schedule" | "show_urgent_items";
      kind: "navigation";
      href: string;
      message: string;
    }
  | {
      intent: "focus_workspace";
      kind: "explanation";
      target: string;
      message: string;
    }
  | {
      intent: "explain_priority";
      kind: "explanation";
      message: string;
    }
  | {
      kind: "message";
      message: string;
    };

export function parseCommandInput(input: string): ParsedCommand {
  const trimmed = input.trim();

  if (!trimmed) {
    return {
      kind: "message",
      message:
        "Try a literal command like build dashboard, create project orbit launch site, create study session OS quiz review, or explain priority.",
    };
  }

  const addTaskMatch = trimmed.match(/^add task\s+(.+)$/i);
  if (addTaskMatch?.[1]?.trim()) {
    return {
      intent: "add_task",
      kind: "add_task",
      message: `Added task: ${addTaskMatch[1].trim()}.`,
      input: {
        title: addTaskMatch[1].trim(),
        kind: "assignment",
      },
    };
  }

  const addBillMatch = trimmed.match(/^add bill\s+(.+)$/i);
  if (addBillMatch?.[1]?.trim()) {
    return {
      intent: "add_task",
      kind: "add_task",
      message: `Added bill: ${addBillMatch[1].trim()}.`,
      input: {
        title: addBillMatch[1].trim(),
        kind: "bill",
      },
    };
  }

  const studySessionMatch = trimmed.match(/^create study session\s+(.+)$/i);
  if (studySessionMatch?.[1]?.trim()) {
    return {
      intent: "create_study_session",
      kind: "add_task",
      message: `Created study session: ${studySessionMatch[1].trim()}.`,
      input: {
        title: studySessionMatch[1].trim(),
        kind: "study_session",
        estimatedMinutes: 50,
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

  const createProjectMatch = trimmed.match(/^create project\s+(.+)$/i);
  if (createProjectMatch?.[1]?.trim()) {
    return {
      intent: "create_project",
      kind: "create_workspace",
      message: `Created project: ${createProjectMatch[1].trim()}.`,
      input: {
        name: createProjectMatch[1].trim(),
        kind: "project",
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

  if (/^(generate weekly plan|make weekly plan|build weekly plan)$/i.test(trimmed)) {
    return {
      intent: "generate_weekly_plan",
      kind: "plan",
      message: "Building a weekly plan now.",
    };
  }

  if (/^(build dashboard|refresh home)$/i.test(trimmed)) {
    return {
      intent: "build_dashboard",
      kind: "dashboard",
      message: "Rebuilding the Home dashboard around the current board state.",
    };
  }

  if (/^(suggest widgets|show widget ideas)$/i.test(trimmed)) {
    return {
      intent: "suggest_widgets",
      kind: "dashboard",
      message: "Suggesting a tighter set of widgets for Home.",
    };
  }

  if (/^(rebalance schedule|rebalance week|rebalance the week)$/i.test(trimmed)) {
    return {
      intent: "rebalance_schedule",
      kind: "navigation",
      href: "/calendar?view=rebalance",
      message: "Opening the calendar so Orbit can rebalance the week.",
    };
  }

  if (/^(show urgent items|urgent items)$/i.test(trimmed)) {
    return {
      intent: "show_urgent_items",
      kind: "navigation",
      href: "/assignments?scope=overdue",
      message: "Opening the urgent assignments view now.",
    };
  }

  const focusWorkspaceMatch = trimmed.match(/^focus workspace\s+(.+)$/i);
  if (focusWorkspaceMatch?.[1]?.trim()) {
    return {
      intent: "focus_workspace",
      kind: "explanation",
      target: focusWorkspaceMatch[1].trim(),
      message: `Focusing workspace: ${focusWorkspaceMatch[1].trim()}.`,
    };
  }

  if (/^(explain priority|why this)$/i.test(trimmed)) {
    return {
      intent: "explain_priority",
      kind: "explanation",
      message: "Explaining why Orbit picked the current priority.",
    };
  }

  return {
    kind: "message",
    message:
      "I can help with add task, add event, add material, build dashboard, suggest widgets, rebalance schedule, focus workspace, create project, create study session, generate weekly plan, explain priority, or show urgent items.",
  };
}

function createReceipt(title: string, lines: string[], href?: string): AssistantReceipt {
  return { title, lines, href };
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
    receipt: createReceipt(
      "Priority explanation",
      recommendation
        ? [
            recommendation.reason,
            ...recommendation.scoreBreakdown,
          ]
        : ["The board is calm enough to choose one meaningful next move."],
      "/home",
    ),
  };
}

export function buildPlanCommandResult(plan: StudyPlan): CommandResult {
  return {
    intent: "generate_weekly_plan",
    kind: "plan",
    message: plan.summary,
    plan,
    receipt: createReceipt(
      "Weekly plan ready",
      plan.steps.map((step) => `${step.title} Â· ${step.minutes} min`),
      "/assistant",
    ),
  };
}

export function buildDashboardCommandResult(
  intent: Extract<CommandIntent, "build_dashboard" | "suggest_widgets">,
  widgets: DashboardWidget[],
): CommandResult {
  return {
    intent,
    kind: "dashboard",
    message:
      intent === "build_dashboard"
        ? "Home has been rebuilt around Orbit's current priorities."
        : "Orbit suggested a sharper widget mix for Home.",
    widgets,
    receipt: createReceipt(
      "Home widgets",
      widgets.map((widget) => widget.title),
      "/home",
    ),
  };
}

export function buildExplanationResult(
  intent: Extract<CommandIntent, "focus_workspace" | "explain_priority">,
  title: string,
  lines: string[],
  href?: string,
): CommandResult {
  return {
    intent,
    kind: "explanation",
    message: title,
    receipt: createReceipt(title, lines, href),
  };
}

