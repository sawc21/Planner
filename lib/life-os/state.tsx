"use client";

import { addDays, parseISO, set } from "date-fns";
import { createContext, useContext, useState } from "react";

import {
  buildApplyPlanCommandResult,
  buildDashboardCommandResult,
  buildFocusNotFoundResult,
  buildPlanCommandResult,
  buildPriorityExplanationResult,
  buildRecommendationCommandResult,
  buildScheduleUpdateResult,
  buildWorkspaceFocusResult,
  INTENT_AFFECTED_SURFACES,
  parseCommandInput,
} from "@/lib/life-os/commands";
import { seedLifeOsData } from "@/lib/life-os/mock-data";
import {
  buildActiveWeeklyPlan,
  computeScheduleRebalance,
  getAtRiskWorkspaces,
  getHomeWidgetData,
  getTodayRecommendations,
  getWorkspaceBundle,
} from "@/lib/life-os/selectors";
import type {
  ActiveWeeklyPlan,
  AddEventInput,
  AddMaterialInput,
  AddTaskInput,
  AssistantActivityEvent,
  CommandIntent,
  CommandResult,
  CreateProjectMilestoneInput,
  CreateWorkspaceInput,
  DashboardWidget,
  DashboardWidgetKind,
  Event,
  LifeOsSnapshot,
  ProjectMilestone,
  ScheduleSuggestion,
  StudyMaterial,
  Task,
  Workspace,
} from "@/lib/life-os/types";

type LogActivityInput = Omit<AssistantActivityEvent, "id" | "at" | "read">;

type LifeOsContextValue = LifeOsSnapshot & {
  focusTodayIds: string[];
  focusedWorkspaceId: string | null;
  commandPanelOpen: boolean;
  lastCommandResult: CommandResult | null;
  commandHistory: CommandResult[];
  activeWeeklyPlan: ActiveWeeklyPlan | null;
  pendingScheduleSuggestions: ScheduleSuggestion[];
  assistantActivity: AssistantActivityEvent[];
  completeTask: (taskId: string) => void;
  startTask: (taskId: string) => void;
  moveTaskToTomorrow: (taskId: string) => void;
  toggleFocusToday: (taskId: string) => void;
  focusWorkspace: (workspaceId: string | null) => void;
  addTask: (input: AddTaskInput) => Task;
  addEvent: (input: AddEventInput) => Event;
  addMaterial: (input: AddMaterialInput) => StudyMaterial;
  createWorkspace: (input: CreateWorkspaceInput) => Workspace;
  addMilestone: (input: CreateProjectMilestoneInput) => ProjectMilestone;
  setWidgets: (widgets: DashboardWidget[]) => void;
  openCommandPanel: () => void;
  closeCommandPanel: () => void;
  clearCommandResult: () => void;
  runCommand: (input: string) => CommandResult;
  setActiveWeeklyPlan: (plan: ActiveWeeklyPlan | null) => void;
  applyActiveWeeklyPlan: () => { applied: number };
  applyScheduleSuggestion: (id: string) => void;
  dismissScheduleSuggestion: (id: string) => void;
  clearScheduleSuggestions: () => void;
  logAssistantActivity: (event: LogActivityInput) => AssistantActivityEvent;
  markActivityRead: (id: string) => void;
  clearActivity: () => void;
};

const LifeOsContext = createContext<LifeOsContextValue | null>(null);

function createId(prefix: string, title: string) {
  return `${prefix}-${title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")}-${Date.now()}`;
}

function shiftToTomorrow(dateValue?: string) {
  if (!dateValue) {
    return undefined;
  }

  const currentDate = parseISO(dateValue);
  const tomorrow = addDays(new Date(), 1);

  return set(tomorrow, {
    hours: currentDate.getHours(),
    minutes: currentDate.getMinutes(),
    seconds: 0,
    milliseconds: 0,
  }).toISOString();
}

function buildTask(input: AddTaskInput, workspaces: Workspace[]): Task {
  const fallbackWorkspace =
    input.primaryWorkspaceId ?? workspaces.find((workspace) => workspace.kind === "course")?.id;
  const nextDay = addDays(new Date(), 1);
  const kind = input.kind ?? "assignment";

  return {
    id: createId("task", input.title),
    primaryWorkspaceId: fallbackWorkspace,
    linkedWorkspaceIds: input.linkedWorkspaceIds ?? [],
    kind,
    title: input.title,
    notes: input.notes,
    status: kind === "bill" ? "todo" : "todo",
    priority: input.priority ?? "medium",
    dueAt: set(nextDay, {
      hours: kind === "bill" ? 17 : kind === "study_session" ? 19 : 18,
      minutes: 0,
      seconds: 0,
      milliseconds: 0,
    }).toISOString(),
    tags: ["quick-add"],
    amount: input.amount,
    estimatedMinutes: input.estimatedMinutes ?? (kind === "bill" ? 10 : 45),
    energy: kind === "bill" ? "low" : kind === "study_session" ? "medium" : "medium",
  };
}

function buildEvent(input: AddEventInput, workspaces: Workspace[]): Event {
  const fallbackWorkspace =
    input.workspaceId ?? workspaces.find((workspace) => workspace.kind === "course")?.id;
  const nextDay = addDays(new Date(), 1);

  return {
    id: createId("event", input.title),
    workspaceId: fallbackWorkspace,
    kind: input.kind ?? "session",
    title: input.title,
    notes: input.notes,
    startAt: set(nextDay, {
      hours: 15,
      minutes: 0,
      seconds: 0,
      milliseconds: 0,
    }).toISOString(),
    endAt: set(nextDay, {
      hours: 15,
      minutes: 45,
      seconds: 0,
      milliseconds: 0,
    }).toISOString(),
    location: input.location,
    priority: input.priority ?? "medium",
    tags: ["quick-add"],
  };
}

function buildMaterial(input: AddMaterialInput, workspaces: Workspace[]): StudyMaterial {
  const fallbackWorkspace =
    input.workspaceId ?? workspaces.find((workspace) => workspace.kind === "course")?.id ?? workspaces[0]?.id;

  return {
    id: createId("material", input.title),
    workspaceId: fallbackWorkspace,
    kind: input.kind ?? "notes",
    title: input.title,
    fileType: "Doc",
    summary: input.summary ?? "Quick-added material placeholder for later context.",
    addedAt: new Date().toISOString(),
  };
}

function buildWorkspace(input: CreateWorkspaceInput): Workspace {
  const kind = input.kind ?? "project";
  const shortLabel =
    input.shortLabel ??
    input.name
      .split(" ")
      .slice(0, 2)
      .map((part) => part.slice(0, 4).toUpperCase())
      .join(" ");

  return {
    id: createId("workspace", input.name),
    name: input.name,
    shortLabel,
    kind,
    colorToken: kind === "course" ? "bg-sky-100 text-sky-950" : "bg-violet-100 text-violet-950",
    icon: kind === "course" ? "graduation-cap" : "rocket",
    ownerLabel: kind === "course" ? "Instructor" : "Orbit project",
    progressSummary: kind === "course" ? "A new course board with room for assignments and grades." : "A fresh project board with room for milestones and linked tasks.",
    active: true,
    creditHours: kind === "course" ? 3 : undefined,
    currentGrade: kind === "course" ? 88 : undefined,
    targetGrade: kind === "course" ? 90 : undefined,
    semesterLabel: kind === "course" ? "Spring 2026" : undefined,
    projectHealth: kind === "project" ? "watch" : undefined,
  };
}

function buildMilestone(input: CreateProjectMilestoneInput): ProjectMilestone {
  return {
    id: createId("milestone", input.title),
    workspaceId: input.workspaceId,
    title: input.title,
    summary: input.summary,
    status: "planned",
    progressPercent: 0,
  };
}

function buildWidgets(snapshot: LifeOsSnapshot): DashboardWidget[] {
  return getHomeWidgetData(snapshot).map((entry, index) => ({
    ...entry.widget,
    order: index,
  }));
}

function applyCompletion(task: Task): Task {
  if (task.status === "done" || task.status === "paid") {
    return task;
  }

  return {
    ...task,
    status: task.kind === "bill" ? "paid" : "done",
    completedAt: new Date().toISOString(),
  };
}

function applyStart(task: Task): Task {
  if (task.status === "done" || task.status === "paid") {
    return task;
  }

  return {
    ...task,
    status: task.kind === "bill" ? task.status : "in_progress",
  };
}

export function LifeOsProvider({
  children,
  initialData = seedLifeOsData,
}: {
  children: React.ReactNode;
  initialData?: LifeOsSnapshot;
}) {
  const [workspaces, setWorkspaces] = useState(initialData.workspaces);
  const [tasks, setTasks] = useState(initialData.tasks);
  const [events, setEvents] = useState(initialData.events);
  const [materials, setMaterials] = useState(initialData.materials);
  const [milestones, setMilestones] = useState(initialData.milestones);
  const [widgets, setWidgetsState] = useState(initialData.widgets);
  const [gradebooks] = useState(initialData.gradebooks);
  const [constraintProfile] = useState(initialData.constraintProfile);
  const [focusTodayIds, setFocusTodayIds] = useState<string[]>([]);
  const [focusedWorkspaceId, setFocusedWorkspaceId] = useState<string | null>(null);
  const [commandPanelOpen, setCommandPanelOpen] = useState(false);
  const [lastCommandResult, setLastCommandResult] = useState<CommandResult | null>(null);
  const [commandHistory, setCommandHistory] = useState<CommandResult[]>([]);
  const [activeWeeklyPlan, setActiveWeeklyPlanState] = useState<ActiveWeeklyPlan | null>(null);
  const [pendingScheduleSuggestions, setPendingScheduleSuggestions] = useState<
    ScheduleSuggestion[]
  >([]);
  const [assistantActivity, setAssistantActivity] = useState<AssistantActivityEvent[]>([]);

  const snapshot: LifeOsSnapshot = {
    workspaces,
    tasks,
    events,
    materials,
    milestones,
    widgets,
    gradebooks,
    constraintProfile,
  };

  const activityIdRef = () => `activity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  const logAssistantActivity = (input: LogActivityInput) => {
    const entry: AssistantActivityEvent = {
      id: activityIdRef(),
      at: new Date().toISOString(),
      read: false,
      ...input,
    };
    setAssistantActivity((current) => [entry, ...current].slice(0, 50));
    return entry;
  };

  const markActivityRead = (id: string) => {
    setAssistantActivity((current) =>
      current.map((entry) => (entry.id === id ? { ...entry, read: true } : entry)),
    );
  };

  const clearActivity = () => {
    setAssistantActivity([]);
  };

  const setActiveWeeklyPlan = (plan: ActiveWeeklyPlan | null) => {
    setActiveWeeklyPlanState(plan);
  };

  const applyActiveWeeklyPlan = () => {
    if (!activeWeeklyPlan) {
      return { applied: 0 };
    }

    let applied = 0;
    const nowIso = new Date().toISOString();
    const newTasks: Task[] = [];
    const updatedSteps = activeWeeklyPlan.steps.map((step) => {
      if (step.applied) {
        return step;
      }

      const newTask: Task = {
        id: createId("task", step.title),
        primaryWorkspaceId: step.workspaceId,
        linkedWorkspaceIds: [],
        kind: "study_session",
        title: step.title,
        notes: step.reason,
        status: "scheduled",
        priority: "medium",
        scheduledAt: step.scheduledFor,
        tags: ["from-plan"],
        estimatedMinutes: step.minutes,
        energy: "medium",
      };
      newTasks.push(newTask);
      applied += 1;

      return {
        ...step,
        applied: true,
        appliedTaskId: newTask.id,
      };
    });

    if (newTasks.length) {
      setTasks((current) => [...newTasks, ...current]);
    }

    setActiveWeeklyPlanState({
      ...activeWeeklyPlan,
      steps: updatedSteps,
      appliedAt: applied > 0 ? nowIso : activeWeeklyPlan.appliedAt,
    });

    return { applied };
  };

  const applyScheduleSuggestion = (id: string) => {
    const suggestion = pendingScheduleSuggestions.find((entry) => entry.id === id);
    if (!suggestion || suggestion.status !== "pending") {
      return;
    }

    if (suggestion.kind === "shift" || suggestion.kind === "reschedule") {
      if (suggestion.taskId) {
        setTasks((current) =>
          current.map((task) =>
            task.id === suggestion.taskId
              ? { ...task, scheduledAt: suggestion.toAt }
              : task,
          ),
        );
      }
    } else if (suggestion.kind === "insert") {
      if (suggestion.taskId) {
        setTasks((current) =>
          current.map((task) =>
            task.id === suggestion.taskId
              ? { ...task, scheduledAt: suggestion.toAt, status: "scheduled" }
              : task,
          ),
        );
      }
    }

    setPendingScheduleSuggestions((current) =>
      current.map((entry) =>
        entry.id === id
          ? { ...entry, status: "applied", appliedAt: new Date().toISOString() }
          : entry,
      ),
    );
  };

  const dismissScheduleSuggestion = (id: string) => {
    setPendingScheduleSuggestions((current) =>
      current.map((entry) =>
        entry.id === id ? { ...entry, status: "dismissed" } : entry,
      ),
    );
  };

  const clearScheduleSuggestions = () => {
    setPendingScheduleSuggestions([]);
  };

  const pushResult = (result: CommandResult) => {
    setLastCommandResult(result);
    if (result.kind !== "message") {
      setCommandHistory((current) => [result, ...current].slice(0, 8));
    }
    return result;
  };

  const logForResult = (
    intent: CommandIntent,
    result: CommandResult,
    title: string,
    summary: string,
    href?: string,
  ) => {
    logAssistantActivity({
      intent,
      title,
      summary,
      affectedSurfaces: INTENT_AFFECTED_SURFACES[intent],
      href,
      receiptLines:
        "receipt" in result && result.receipt ? result.receipt.lines : [],
      resultKind: result.kind,
    });
  };

  const completeTask = (taskId: string) => {
    setTasks((current) => current.map((task) => (task.id === taskId ? applyCompletion(task) : task)));
    setFocusTodayIds((current) => current.filter((entry) => entry !== taskId));
  };

  const startTask = (taskId: string) => {
    setTasks((current) => current.map((task) => (task.id === taskId ? applyStart(task) : task)));
    setFocusTodayIds((current) => (current.includes(taskId) ? current : [...current, taskId]));
  };

  const moveTaskToTomorrow = (taskId: string) => {
    setTasks((current) =>
      current.map((task) =>
        task.id === taskId
          ? {
              ...task,
              dueAt: shiftToTomorrow(task.dueAt),
              scheduledAt: shiftToTomorrow(task.scheduledAt),
              deferredUntil: shiftToTomorrow(task.dueAt ?? task.scheduledAt),
            }
          : task,
      ),
    );
    setFocusTodayIds((current) => current.filter((entry) => entry !== taskId));
  };

  const toggleFocusToday = (taskId: string) => {
    setFocusTodayIds((current) =>
      current.includes(taskId)
        ? current.filter((entry) => entry !== taskId)
        : [...current, taskId],
    );
  };

  const focusWorkspace = (workspaceId: string | null) => {
    setFocusedWorkspaceId(workspaceId);
  };

  const addTask = (input: AddTaskInput) => {
    const task = buildTask(input, workspaces);
    setTasks((current) => [task, ...current]);
    return task;
  };

  const addEvent = (input: AddEventInput) => {
    const event = buildEvent(input, workspaces);
    setEvents((current) => [event, ...current]);
    return event;
  };

  const addMaterial = (input: AddMaterialInput) => {
    const material = buildMaterial(input, workspaces);
    setMaterials((current) => [material, ...current]);
    return material;
  };

  const createWorkspace = (input: CreateWorkspaceInput) => {
    const workspace = buildWorkspace(input);
    setWorkspaces((current) => [workspace, ...current]);
    return workspace;
  };

  const addMilestone = (input: CreateProjectMilestoneInput) => {
    const milestone = buildMilestone(input);
    setMilestones((current) => [milestone, ...current]);
    return milestone;
  };

  const setWidgets = (nextWidgets: DashboardWidget[]) => {
    setWidgetsState(nextWidgets);
  };

  const openCommandPanel = () => setCommandPanelOpen(true);
  const closeCommandPanel = () => setCommandPanelOpen(false);
  const clearCommandResult = () => setLastCommandResult(null);

  const runCommand = (input: string) => {
    const parsed = parseCommandInput(input);

    if (parsed.kind === "message") {
      setLastCommandResult(parsed);
      return parsed;
    }

    if (parsed.kind === "add_task") {
      const task = addTask(parsed.input);
      const result = pushResult({
        intent: parsed.intent,
        kind: "mutation",
        message: parsed.message,
        taskId: task.id,
        receipt: {
          title: parsed.intent === "create_study_session" ? "Study session created" : "Task created",
          lines: [task.title, task.primaryWorkspaceId ? "Linked to a workspace" : "Independent task"],
          href: "/assignments",
        },
      });
      logForResult(parsed.intent, result, parsed.intent === "create_study_session" ? "Study session created" : "Task created", task.title, "/assignments");
      return result;
    }

    if (parsed.kind === "add_event") {
      const event = addEvent(parsed.input);
      const result = pushResult({
        intent: parsed.intent,
        kind: "mutation",
        message: parsed.message,
        eventId: event.id,
        receipt: {
          title: "Event created",
          lines: [event.title, "Orbit added it to the calendar surface."],
          href: "/calendar",
        },
      });
      logForResult(parsed.intent, result, "Event created", event.title, "/calendar");
      return result;
    }

    if (parsed.kind === "add_material") {
      const material = addMaterial(parsed.input);
      const result = pushResult({
        intent: parsed.intent,
        kind: "mutation",
        message: parsed.message,
        materialId: material.id,
        receipt: {
          title: "Material added",
          lines: [material.title, material.summary],
        },
      });
      logForResult(parsed.intent, result, "Material added", material.title);
      return result;
    }

    if (parsed.kind === "create_workspace") {
      const workspace = createWorkspace(parsed.input);
      const result = pushResult({
        intent: parsed.intent,
        kind: "mutation",
        message: parsed.message,
        workspaceId: workspace.id,
        receipt: {
          title: "Project created",
          lines: [workspace.name, workspace.progressSummary],
          href: `/workspaces/${workspace.id}`,
        },
      });
      logForResult(parsed.intent, result, "Project created", workspace.name, `/workspaces/${workspace.id}`);
      return result;
    }

    if (parsed.kind === "recommendation") {
      const recommendation = getTodayRecommendations(snapshot).primary;
      const result = pushResult(buildRecommendationCommandResult(recommendation));
      logForResult(
        parsed.intent,
        result,
        "Recommendation ready",
        recommendation ? `Start with ${recommendation.item.title}.` : "Board is calm right now.",
        "/home",
      );
      return result;
    }

    if (parsed.kind === "plan") {
      const plan = buildActiveWeeklyPlan(snapshot, new Date(), focusedWorkspaceId ?? undefined);
      setActiveWeeklyPlanState(plan);
      const result = pushResult(buildPlanCommandResult(plan));
      logForResult(
        parsed.intent,
        result,
        "Weekly plan ready",
        `${plan.steps.length} step plan drafted for this week.`,
        "/assistant",
      );
      return result;
    }

    if (parsed.kind === "apply_plan") {
      const { applied } = applyActiveWeeklyPlan();
      const totalSteps = activeWeeklyPlan?.steps.length ?? 0;
      const result = pushResult(
        buildApplyPlanCommandResult(applied, totalSteps, activeWeeklyPlan),
      );
      logForResult(
        parsed.intent,
        result,
        "Plan applied",
        activeWeeklyPlan
          ? `Scheduled ${applied} step${applied === 1 ? "" : "s"} on the calendar.`
          : "No plan to apply yet.",
        "/calendar",
      );
      return result;
    }

    if (parsed.kind === "dashboard") {
      const previousKinds = new Set<DashboardWidgetKind>(widgets.map((widget) => widget.kind));
      const nextWidgets = buildWidgets(snapshot);
      const nextKinds = new Set<DashboardWidgetKind>(nextWidgets.map((widget) => widget.kind));
      const added = [...nextKinds].filter((kind) => !previousKinds.has(kind));
      const removed = [...previousKinds].filter((kind) => !nextKinds.has(kind));

      setWidgetsState(nextWidgets);
      const result = pushResult(
        buildDashboardCommandResult(parsed.intent, nextWidgets, added, removed),
      );
      logForResult(
        parsed.intent,
        result,
        parsed.intent === "build_dashboard" ? "Home rebuilt" : "Widgets suggested",
        `${nextWidgets.length} widgets pinned to Home.`,
        "/home",
      );
      return result;
    }

    if (parsed.kind === "rebalance") {
      const suggestions = computeScheduleRebalance(snapshot, new Date());
      setPendingScheduleSuggestions(suggestions);
      const result = pushResult(buildScheduleUpdateResult(suggestions));
      logForResult(
        parsed.intent,
        result,
        "Schedule rebalance",
        suggestions.length
          ? `${suggestions.length} schedule move${suggestions.length === 1 ? "" : "s"} suggested.`
          : "Week already balances.",
        "/calendar",
      );
      return result;
    }

    if (parsed.kind === "focus_workspace") {
      const matchedWorkspace = workspaces.find(
        (workspace) =>
          workspace.name.toLowerCase().includes(parsed.target.toLowerCase()) ||
          workspace.shortLabel.toLowerCase().includes(parsed.target.toLowerCase()),
      );

      if (!matchedWorkspace) {
        const result = pushResult(buildFocusNotFoundResult(parsed.target));
        logForResult(
          parsed.intent,
          result,
          "Workspace not found",
          `No workspace matched "${parsed.target}".`,
          "/workspaces",
        );
        return result;
      }

      setFocusedWorkspaceId(matchedWorkspace.id);
      const bundle = getWorkspaceBundle(snapshot, matchedWorkspace.id);
      const result = pushResult(
        buildWorkspaceFocusResult(
          matchedWorkspace,
          bundle?.tasks.length ?? 0,
          bundle?.milestones.length ?? 0,
        ),
      );
      logForResult(
        parsed.intent,
        result,
        `Focus ${matchedWorkspace.shortLabel}`,
        matchedWorkspace.progressSummary,
        `/workspaces/${matchedWorkspace.id}`,
      );
      return result;
    }

    if (parsed.kind === "clear_focus") {
      setFocusedWorkspaceId(null);
      const result = pushResult(buildWorkspaceFocusResult(null, 0, 0));
      logForResult(
        parsed.intent,
        result,
        "Focus cleared",
        "Home ranking back to default mix.",
        "/home",
      );
      return result;
    }

    if (parsed.kind === "explain") {
      const recommendation = getTodayRecommendations(snapshot).primary;
      const atRisk = getAtRiskWorkspaces(snapshot, new Date(), 1)[0];
      const result = pushResult(
        buildPriorityExplanationResult(recommendation, atRisk?.reason),
      );
      logForResult(
        parsed.intent,
        result,
        "Why Orbit picked this",
        recommendation
          ? `Chose ${recommendation.item.title}.`
          : "Board is calm right now.",
        "/home",
      );
      return result;
    }

    // Navigation (show_urgent_items)
    const result = pushResult({
      intent: parsed.intent,
      kind: "navigation",
      message: parsed.message,
      href: parsed.href,
      receipt: {
        title: "Navigation ready",
        lines: [parsed.message],
        href: parsed.href,
      },
    });
    logForResult(parsed.intent, result, "Navigation ready", parsed.message, parsed.href);
    return result;
  };

  const value: LifeOsContextValue = {
    ...snapshot,
    focusTodayIds,
    focusedWorkspaceId,
    commandPanelOpen,
    lastCommandResult,
    commandHistory,
    activeWeeklyPlan,
    pendingScheduleSuggestions,
    assistantActivity,
    completeTask,
    startTask,
    moveTaskToTomorrow,
    toggleFocusToday,
    focusWorkspace,
    addTask,
    addEvent,
    addMaterial,
    createWorkspace,
    addMilestone,
    setWidgets,
    openCommandPanel,
    closeCommandPanel,
    clearCommandResult,
    runCommand,
    setActiveWeeklyPlan,
    applyActiveWeeklyPlan,
    applyScheduleSuggestion,
    dismissScheduleSuggestion,
    clearScheduleSuggestions,
    logAssistantActivity,
    markActivityRead,
    clearActivity,
  };

  return <LifeOsContext.Provider value={value}>{children}</LifeOsContext.Provider>;
}

export function useLifeOs() {
  const context = useContext(LifeOsContext);

  if (!context) {
    throw new Error("useLifeOs must be used within a LifeOsProvider.");
  }

  return context;
}
