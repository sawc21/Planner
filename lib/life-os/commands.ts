import type {
  ActiveWeeklyPlan,
  AddEventInput,
  AddMaterialInput,
  AddTaskInput,
  AssistantActivitySurface,
  AssistantReceipt,
  CommandIntent,
  CommandResult,
  CreateWorkspaceInput,
  DashboardWidget,
  DashboardWidgetKind,
  ScheduleSuggestion,
  TodayRecommendation,
  Workspace,
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
      intent: "apply_weekly_plan";
      kind: "apply_plan";
      message: string;
    }
  | {
      intent: "build_dashboard" | "suggest_widgets";
      kind: "dashboard";
      message: string;
    }
  | {
      intent: "rebalance_schedule";
      kind: "rebalance";
      message: string;
    }
  | {
      intent: "show_urgent_items";
      kind: "navigation";
      href: string;
      message: string;
    }
  | {
      intent: "focus_workspace";
      kind: "focus_workspace";
      target: string;
      message: string;
    }
  | {
      intent: "focus_workspace";
      kind: "clear_focus";
      message: string;
    }
  | {
      intent: "explain_priority";
      kind: "explain";
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

  if (/^(apply weekly plan|apply plan|schedule weekly plan)$/i.test(trimmed)) {
    return {
      intent: "apply_weekly_plan",
      kind: "apply_plan",
      message: "Applying the active weekly plan to this week.",
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
      kind: "rebalance",
      message: "Rebalancing this week around current load.",
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

  if (/^(clear focus|remove focus|unfocus workspace|clear workspace focus)$/i.test(trimmed)) {
    return {
      intent: "focus_workspace",
      kind: "clear_focus",
      message: "Cleared the workspace focus.",
    };
  }

  const focusWorkspaceMatch = trimmed.match(/^focus workspace\s+(.+)$/i);
  if (focusWorkspaceMatch?.[1]?.trim()) {
    return {
      intent: "focus_workspace",
      kind: "focus_workspace",
      target: focusWorkspaceMatch[1].trim(),
      message: `Focusing workspace: ${focusWorkspaceMatch[1].trim()}.`,
    };
  }

  if (/^(explain priority|why this)$/i.test(trimmed)) {
    return {
      intent: "explain_priority",
      kind: "explain",
      message: "Explaining why Orbit picked the current priority.",
    };
  }

  return {
    kind: "message",
    message:
      "I can help with add task, add event, add material, build dashboard, suggest widgets, rebalance schedule, focus workspace, clear focus, create project, create study session, generate weekly plan, apply weekly plan, explain priority, or show urgent items.",
  };
}

export const INTENT_AFFECTED_SURFACES: Record<CommandIntent, AssistantActivitySurface[]> = {
  add_task: ["assignments", "calendar", "home"],
  add_event: ["calendar", "home"],
  add_material: ["workspaces"],
  build_dashboard: ["home"],
  suggest_widgets: ["home"],
  rebalance_schedule: ["calendar", "home"],
  focus_workspace: ["workspaces", "home", "assistant"],
  create_project: ["workspaces", "home"],
  create_study_session: ["calendar", "assignments", "home"],
  generate_weekly_plan: ["home", "calendar", "assistant"],
  apply_weekly_plan: ["calendar", "assignments", "home"],
  explain_priority: ["assistant", "home"],
  what_should_i_do_today: ["home", "assistant"],
  show_urgent_items: ["assignments", "home"],
};

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
        ? [recommendation.reason, ...recommendation.scoreBreakdown]
        : ["The board is calm enough to choose one meaningful next move."],
      "/home",
    ),
  };
}

export function buildPlanCommandResult(plan: ActiveWeeklyPlan): CommandResult {
  const appliedCount = plan.steps.filter((step) => step.applied).length;

  return {
    intent: "generate_weekly_plan",
    kind: "plan_update",
    message: plan.summary,
    plan,
    appliedCount,
    receipt: createReceipt(
      "Weekly plan ready",
      plan.steps.map((step) => `${step.title} · ${step.minutes} min`),
      "/assistant",
    ),
  };
}

export function buildApplyPlanCommandResult(
  appliedCount: number,
  totalSteps: number,
  plan: ActiveWeeklyPlan | null,
): CommandResult {
  return {
    intent: "apply_weekly_plan",
    kind: "action_receipt",
    message: plan
      ? `Applied ${appliedCount} of ${totalSteps} plan steps to this week.`
      : "No active weekly plan to apply yet. Generate one first.",
    receipt: createReceipt(
      "Plan applied",
      plan
        ? plan.steps
            .filter((step) => step.applied)
            .map((step) => `${step.title} · scheduled`)
        : ["Run generate weekly plan to build one."],
      "/calendar",
    ),
    actions: plan
      ? [
          { label: "Open calendar", href: "/calendar" },
          { label: "Open assignments", href: "/assignments" },
        ]
      : [{ label: "Generate plan", intent: "generate_weekly_plan" }],
  };
}

export function buildDashboardCommandResult(
  intent: Extract<CommandIntent, "build_dashboard" | "suggest_widgets">,
  widgets: DashboardWidget[],
  added: DashboardWidgetKind[],
  removed: DashboardWidgetKind[],
): CommandResult {
  return {
    intent,
    kind: "dashboard_update",
    message:
      intent === "build_dashboard"
        ? "Home has been rebuilt around Orbit's current priorities."
        : "Orbit suggested a sharper widget mix for Home.",
    widgets,
    added,
    removed,
    receipt: createReceipt(
      "Home widgets",
      [
        ...widgets.map((widget) => widget.title),
        ...(added.length ? [`Added: ${added.join(", ")}`] : []),
        ...(removed.length ? [`Removed: ${removed.join(", ")}`] : []),
      ],
      "/home",
    ),
  };
}

export function buildWorkspaceFocusResult(
  workspace: Workspace | null,
  linkedTaskCount: number,
  milestoneCount: number,
): CommandResult {
  if (!workspace) {
    return {
      intent: "focus_workspace",
      kind: "workspace_focus",
      message: "Cleared the workspace focus.",
      workspaceId: null,
      affectedSurfaces: INTENT_AFFECTED_SURFACES.focus_workspace,
      receipt: createReceipt(
        "Focus cleared",
        ["Home ranking and workspace card rings are back to the default mix."],
        "/home",
      ),
    };
  }

  return {
    intent: "focus_workspace",
    kind: "workspace_focus",
    message: `Focused workspace: ${workspace.name}.`,
    workspaceId: workspace.id,
    affectedSurfaces: INTENT_AFFECTED_SURFACES.focus_workspace,
    receipt: createReceipt(
      `Focus ${workspace.shortLabel}`,
      [
        workspace.progressSummary,
        `${linkedTaskCount} linked tasks and ${milestoneCount} milestones are visible.`,
      ],
      `/workspaces/${workspace.id}`,
    ),
  };
}

export function buildFocusNotFoundResult(target: string): CommandResult {
  return {
    intent: "focus_workspace",
    kind: "workspace_focus",
    message: `No workspace matched "${target}".`,
    workspaceId: null,
    affectedSurfaces: INTENT_AFFECTED_SURFACES.focus_workspace,
    receipt: createReceipt(
      "Workspace not found",
      ["Try a workspace name or short label that exists on the board."],
      "/workspaces",
    ),
  };
}

export function buildPriorityExplanationResult(
  recommendation: TodayRecommendation | undefined,
  atRiskReason?: string,
): CommandResult {
  return {
    intent: "explain_priority",
    kind: "priority_explanation",
    message: recommendation
      ? `Start with ${recommendation.item.title}. ${recommendation.reason}`
      : "The board is calm enough that no single item is dominating the day.",
    recommendation,
    affectedSurfaces: INTENT_AFFECTED_SURFACES.explain_priority,
    receipt: createReceipt(
      "Why Orbit picked this",
      recommendation
        ? [
            recommendation.reason,
            recommendation.explanation,
            atRiskReason ?? "No workspace is clearly slipping.",
          ]
        : ["The board is calm enough that no single item is dominating the day."],
      "/home",
    ),
  };
}

export function buildScheduleUpdateResult(
  suggestions: ScheduleSuggestion[],
): CommandResult {
  const pending = suggestions.filter((entry) => entry.status === "pending");
  return {
    intent: "rebalance_schedule",
    kind: "schedule_update",
    message: suggestions.length
      ? `Orbit suggested ${pending.length} schedule move${pending.length === 1 ? "" : "s"} for the week.`
      : "No schedule changes needed — the week already balances.",
    suggestions,
    receipt: createReceipt(
      "Schedule rebalance",
      suggestions.length
        ? suggestions.map((entry) => `${entry.title} · ${entry.reason}`)
        : ["The week already fits within open windows."],
      "/calendar",
    ),
  };
}
