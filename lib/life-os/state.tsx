"use client";

import { addDays, parseISO, set } from "date-fns";
import { createContext, useContext, useState } from "react";

import {
  buildDashboardCommandResult,
  buildExplanationResult,
  buildPlanCommandResult,
  buildRecommendationCommandResult,
  parseCommandInput,
} from "@/lib/life-os/commands";
import { seedLifeOsData } from "@/lib/life-os/mock-data";
import {
  getAtRiskWorkspaces,
  getConstraintAwarePlan,
  getHomeWidgetData,
  getTodayRecommendations,
  getWorkspaceBundle,
} from "@/lib/life-os/selectors";
import type {
  AddEventInput,
  AddMaterialInput,
  AddTaskInput,
  CommandResult,
  CreateProjectMilestoneInput,
  CreateWorkspaceInput,
  DashboardWidget,
  Event,
  LifeOsSnapshot,
  ProjectMilestone,
  StudyMaterial,
  Task,
  Workspace,
} from "@/lib/life-os/types";

type LifeOsContextValue = LifeOsSnapshot & {
  focusTodayIds: string[];
  focusedWorkspaceId: string | null;
  commandPanelOpen: boolean;
  lastCommandResult: CommandResult | null;
  commandHistory: CommandResult[];
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

  const pushResult = (result: CommandResult) => {
    setLastCommandResult(result);
    if (result.kind !== "message") {
      setCommandHistory((current) => [result, ...current].slice(0, 8));
    }
    return result;
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
      return pushResult({
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
    }

    if (parsed.kind === "add_event") {
      const event = addEvent(parsed.input);
      return pushResult({
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
    }

    if (parsed.kind === "add_material") {
      const material = addMaterial(parsed.input);
      return pushResult({
        intent: parsed.intent,
        kind: "mutation",
        message: parsed.message,
        materialId: material.id,
        receipt: {
          title: "Material added",
          lines: [material.title, material.summary],
        },
      });
    }

    if (parsed.kind === "create_workspace") {
      const workspace = createWorkspace(parsed.input);
      return pushResult({
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
    }

    if (parsed.kind === "recommendation") {
      return pushResult(buildRecommendationCommandResult(getTodayRecommendations(snapshot).primary));
    }

    if (parsed.kind === "plan") {
      return pushResult(buildPlanCommandResult(getConstraintAwarePlan(snapshot, focusedWorkspaceId ?? undefined)));
    }

    if (parsed.kind === "dashboard") {
      const nextWidgets = buildWidgets(snapshot);
      setWidgetsState(nextWidgets);
      return pushResult(buildDashboardCommandResult(parsed.intent, nextWidgets));
    }

    if (parsed.kind === "explanation") {
      if (parsed.intent === "focus_workspace") {
        const matchedWorkspace = workspaces.find((workspace) =>
          workspace.name.toLowerCase().includes(parsed.target.toLowerCase()) ||
          workspace.shortLabel.toLowerCase().includes(parsed.target.toLowerCase()),
        );

        if (!matchedWorkspace) {
          return pushResult(
            buildExplanationResult(
              parsed.intent,
              "Workspace not found",
              ["Try a workspace name or short label that exists on the board."],
            ),
          );
        }

        setFocusedWorkspaceId(matchedWorkspace.id);
        const bundle = getWorkspaceBundle(snapshot, matchedWorkspace.id);
        return pushResult(
          buildExplanationResult(
            parsed.intent,
            `Focus ${matchedWorkspace.shortLabel}`,
            [
              matchedWorkspace.progressSummary,
              `${bundle?.tasks.length ?? 0} linked tasks and ${bundle?.milestones.length ?? 0} milestones are visible.`,
            ],
            `/workspaces/${matchedWorkspace.id}`,
          ),
        );
      }

      const recommendation = getTodayRecommendations(snapshot).primary;
      const atRisk = getAtRiskWorkspaces(snapshot, new Date(), 1)[0];
      return pushResult(
        buildExplanationResult(
          parsed.intent,
          "Why Orbit picked this",
          recommendation
            ? [recommendation.reason, recommendation.explanation, atRisk ? atRisk.reason : "No workspace is clearly slipping."]
            : ["The board is calm enough that no single item is dominating the day."],
          "/home",
        ),
      );
    }

    return pushResult({
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
  };

  const value: LifeOsContextValue = {
    ...snapshot,
    focusTodayIds,
    focusedWorkspaceId,
    commandPanelOpen,
    lastCommandResult,
    commandHistory,
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

