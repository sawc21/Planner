"use client";

import { addDays, parseISO, set } from "date-fns";
import { createContext, useContext, useState } from "react";

import {
  buildPlanCommandResult,
  buildRecommendationCommandResult,
  parseCommandInput,
} from "@/lib/life-os/commands";
import { seedLifeOsData } from "@/lib/life-os/mock-data";
import {
  getConstraintAwarePlan,
  getTodayRecommendations,
} from "@/lib/life-os/selectors";
import type {
  AddEventInput,
  AddMaterialInput,
  AddTaskInput,
  CommandResult,
  CreateWorkspaceInput,
  Event,
  LifeOsSnapshot,
  StudyMaterial,
  Task,
  Workspace,
} from "@/lib/life-os/types";

type LifeOsContextValue = LifeOsSnapshot & {
  focusTodayIds: string[];
  commandPanelOpen: boolean;
  lastCommandResult: CommandResult | null;
  completeTask: (taskId: string) => void;
  startTask: (taskId: string) => void;
  moveTaskToTomorrow: (taskId: string) => void;
  toggleFocusToday: (taskId: string) => void;
  addTask: (input: AddTaskInput) => Task;
  addEvent: (input: AddEventInput) => Event;
  addMaterial: (input: AddMaterialInput) => StudyMaterial;
  createWorkspace: (input: CreateWorkspaceInput) => Workspace;
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
    input.workspaceId ??
    workspaces.find((workspace) => workspace.kind === "personal")?.id ??
    workspaces[0]?.id;

  const nextDay = addDays(new Date(), 1);
  const kind = input.kind ?? "assignment";

  return {
    id: createId("task", input.title),
    workspaceId: fallbackWorkspace,
    kind,
    title: input.title,
    notes: input.notes,
    status: kind === "bill" ? "todo" : "todo",
    priority: input.priority ?? "medium",
    dueAt: set(nextDay, {
      hours: kind === "bill" ? 17 : 18,
      minutes: 0,
      seconds: 0,
      milliseconds: 0,
    }).toISOString(),
    tags: ["quick-add"],
    amount: input.amount,
    estimatedMinutes: input.estimatedMinutes ?? (kind === "bill" ? 10 : 35),
    energy: kind === "bill" ? "low" : "medium",
  };
}

function buildEvent(input: AddEventInput, workspaces: Workspace[]): Event {
  const fallbackWorkspace =
    input.workspaceId ??
    workspaces.find((workspace) => workspace.kind === "course")?.id ??
    workspaces[0]?.id;
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
    input.workspaceId ??
    workspaces.find((workspace) => workspace.kind === "course" || workspace.kind === "study_track")
      ?.id ??
    workspaces[0]?.id;

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
  const kind = input.kind ?? "study_track";
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
    colorToken:
      kind === "course"
        ? "bg-sky-100 text-sky-900"
        : kind === "study_track"
          ? "bg-emerald-100 text-emerald-900"
          : kind === "work"
            ? "bg-violet-100 text-violet-900"
            : "bg-stone-200 text-stone-900",
    icon:
      kind === "course"
        ? "graduation-cap"
        : kind === "study_track"
          ? "compass"
          : kind === "work"
            ? "briefcase"
            : "wallet",
    ownerLabel: kind === "course" ? "Instructor" : "Self-managed",
    progressSummary: "A fresh workspace with room to add context.",
  };
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
  const [gradebooks] = useState(initialData.gradebooks);
  const [progressRecords] = useState(initialData.progressRecords);
  const [constraintProfile] = useState(initialData.constraintProfile);
  const [focusTodayIds, setFocusTodayIds] = useState<string[]>([]);
  const [commandPanelOpen, setCommandPanelOpen] = useState(false);
  const [lastCommandResult, setLastCommandResult] = useState<CommandResult | null>(null);

  const snapshot: LifeOsSnapshot = {
    workspaces,
    tasks,
    events,
    materials,
    gradebooks,
    progressRecords,
    constraintProfile,
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
      const result: CommandResult = {
        intent: parsed.intent,
        kind: "mutation",
        message: parsed.message,
        taskId: task.id,
      };
      setLastCommandResult(result);
      return result;
    }

    if (parsed.kind === "add_event") {
      const event = addEvent(parsed.input);
      const result: CommandResult = {
        intent: parsed.intent,
        kind: "mutation",
        message: parsed.message,
        eventId: event.id,
      };
      setLastCommandResult(result);
      return result;
    }

    if (parsed.kind === "add_material") {
      const material = addMaterial(parsed.input);
      const result: CommandResult = {
        intent: parsed.intent,
        kind: "mutation",
        message: parsed.message,
        materialId: material.id,
      };
      setLastCommandResult(result);
      return result;
    }

    if (parsed.kind === "create_workspace") {
      const workspace = createWorkspace(parsed.input);
      const result: CommandResult = {
        intent: parsed.intent,
        kind: "mutation",
        message: parsed.message,
        workspaceId: workspace.id,
      };
      setLastCommandResult(result);
      return result;
    }

    if (parsed.kind === "recommendation") {
      const result = buildRecommendationCommandResult(
        getTodayRecommendations(snapshot).primary,
      );
      setLastCommandResult(result);
      return result;
    }

    if (parsed.kind === "plan") {
      const result = buildPlanCommandResult(getConstraintAwarePlan(snapshot));
      setLastCommandResult(result);
      return result;
    }

    const result: CommandResult = {
      intent: parsed.intent,
      kind: "navigation",
      message: parsed.message,
      href: parsed.href,
    };
    setLastCommandResult(result);
    return result;
  };

  const value: LifeOsContextValue = {
    ...snapshot,
    focusTodayIds,
    commandPanelOpen,
    lastCommandResult,
    completeTask,
    startTask,
    moveTaskToTomorrow,
    toggleFocusToday,
    addTask,
    addEvent,
    addMaterial,
    createWorkspace,
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
