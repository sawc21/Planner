export const WORKSPACE_KINDS = [
  "course",
  "study_track",
  "personal",
  "work",
  "admin",
] as const;

export const TASK_KINDS = [
  "assignment",
  "study_session",
  "admin",
  "bill",
  "errand",
  "work_task",
] as const;

export const TASK_STATUSES = [
  "todo",
  "in_progress",
  "done",
  "scheduled",
  "paid",
  "snoozed",
] as const;

export const TASK_PRIORITIES = [
  "low",
  "medium",
  "high",
  "critical",
] as const;

export const ENERGY_LEVELS = ["low", "medium", "high"] as const;

export const EVENT_KINDS = [
  "class",
  "office_hours",
  "appointment",
  "review",
  "exam",
  "session",
] as const;

export const MATERIAL_KINDS = [
  "syllabus",
  "notes",
  "assignment",
  "spec",
  "study_guide",
  "pdf",
  "image",
] as const;

export type WorkspaceKind = (typeof WORKSPACE_KINDS)[number];
export type TaskKind = (typeof TASK_KINDS)[number];
export type TaskStatus = (typeof TASK_STATUSES)[number];
export type TaskPriority = (typeof TASK_PRIORITIES)[number];
export type EnergyLevel = (typeof ENERGY_LEVELS)[number];
export type EventKind = (typeof EVENT_KINDS)[number];
export type MaterialKind = (typeof MATERIAL_KINDS)[number];

export type Workspace = {
  id: string;
  name: string;
  shortLabel: string;
  kind: WorkspaceKind;
  colorToken: string;
  icon: string;
  ownerLabel: string;
  progressSummary: string;
  creditHours?: number;
  currentGrade?: number;
  targetGrade?: number;
};

export type Task = {
  id: string;
  workspaceId: string;
  kind: TaskKind;
  title: string;
  notes?: string;
  status: TaskStatus;
  priority: TaskPriority;
  dueAt?: string;
  scheduledAt?: string;
  completedAt?: string;
  tags: string[];
  location?: string;
  amount?: number;
  estimatedMinutes?: number;
  energy: EnergyLevel;
  recurring?: boolean;
  deferredUntil?: string;
};

export type Event = {
  id: string;
  workspaceId: string;
  kind: EventKind;
  title: string;
  notes?: string;
  startAt: string;
  endAt?: string;
  location?: string;
  priority: TaskPriority;
  tags: string[];
};

export type StudyMaterial = {
  id: string;
  workspaceId: string;
  kind: MaterialKind;
  title: string;
  fileType: string;
  summary: string;
  addedAt: string;
  relatedTaskIds?: string[];
};

export type GradeCategory = {
  id: string;
  label: string;
  weight: number;
  currentScore: number;
};

export type GradeItem = {
  id: string;
  workspaceId: string;
  categoryId: string;
  title: string;
  weight: number;
  maxScore: number;
  score?: number;
  dueAt?: string;
  status: "graded" | "planned";
};

export type Gradebook = {
  workspaceId: string;
  currentGrade: number;
  targetGrade: number;
  categories: GradeCategory[];
  items: GradeItem[];
};

export type ProgressRecord = {
  id: string;
  workspaceId: string;
  label: string;
  currentValue: number;
  targetValue: number;
  unit: string;
  confidence: "low" | "medium" | "high";
  dueAt?: string;
};

export type ConstraintProfile = {
  weeklyHoursAvailable: number;
  weeklyBudgetAvailable: number;
  hoursRemainingThisWeek: number;
  budgetRemainingThisWeek: number;
  defaultEnergyProfile: EnergyLevel;
};

export type StudyPlanStep = {
  id: string;
  title: string;
  reason: string;
  minutes: number;
  workspaceId: string;
};

export type StudyPlan = {
  title: string;
  summary: string;
  steps: StudyPlanStep[];
};

export type TaskView = Task & {
  workspace: Workspace;
};

export type EventView = Event & {
  workspace: Workspace;
};

export type TodayRecommendation = {
  item: TaskView;
  score: number;
  reason: string;
  explanation: string;
  scoreBreakdown: string[];
};

export type TodayRecommendationResult = {
  primary?: TodayRecommendation;
  secondary: TodayRecommendation[];
};

export type OverloadAssessment = {
  isOverloaded: boolean;
  severity: "calm" | "watch" | "overloaded";
  reason: string;
  suggestedAction: string;
};

export type AgendaEntry = {
  id: string;
  kind: "task" | "event";
  timestamp: string;
  task?: TaskView;
  event?: EventView;
};

export type AgendaDayGroup = {
  key: string;
  label: string;
  date: Date;
  isToday: boolean;
  pressureLabel: string;
  entries: AgendaEntry[];
};

export type WorkspaceRisk = {
  workspace: Workspace;
  score: number;
  reason: string;
  signals: string[];
};

export type StudyBuddyInsight = {
  title: string;
  summary: string;
  bullets: string[];
  actionLabel: string;
  actionHref: string;
};

export type ProgressCard = {
  workspace: Workspace;
  title: string;
  detail: string;
  currentValue: number;
  targetValue?: number;
  neededOnNext?: number;
};

export type TaskScope = "all" | "today" | "overdue" | "upcoming";

export type TaskFilterState = {
  query: string;
  workspaceId: string | "all";
  kind: TaskKind | "all";
  status: TaskStatus | "all";
  priority: TaskPriority | "all";
  scope: TaskScope;
};

export type AddTaskInput = {
  title: string;
  workspaceId?: string;
  kind?: TaskKind;
  notes?: string;
  priority?: TaskPriority;
  estimatedMinutes?: number;
  amount?: number;
};

export type AddEventInput = {
  title: string;
  workspaceId?: string;
  kind?: EventKind;
  notes?: string;
  priority?: TaskPriority;
  location?: string;
};

export type AddMaterialInput = {
  title: string;
  workspaceId?: string;
  kind?: MaterialKind;
  summary?: string;
};

export type CreateWorkspaceInput = {
  name: string;
  shortLabel?: string;
  kind?: WorkspaceKind;
};

export type CommandIntent =
  | "add_task"
  | "add_event"
  | "add_material"
  | "create_workspace"
  | "what_should_i_do_today"
  | "build_study_flow"
  | "show_at_risk_workspaces"
  | "rebalance_week"
  | "show_urgent_items";

export type CommandResult =
  | {
      intent: CommandIntent;
      kind: "mutation";
      message: string;
      taskId?: string;
      workspaceId?: string;
      materialId?: string;
      eventId?: string;
    }
  | {
      intent: CommandIntent;
      kind: "navigation";
      message: string;
      href: string;
    }
  | {
      intent: CommandIntent;
      kind: "recommendation";
      message: string;
      recommendation?: TodayRecommendation;
    }
  | {
      intent: CommandIntent;
      kind: "plan";
      message: string;
      plan: StudyPlan;
    }
  | {
      kind: "message";
      message: string;
    };

export type LifeOsSnapshot = {
  workspaces: Workspace[];
  tasks: Task[];
  events: Event[];
  materials: StudyMaterial[];
  gradebooks: Gradebook[];
  progressRecords: ProgressRecord[];
  constraintProfile: ConstraintProfile;
};

export const WORKSPACE_KIND_LABELS: Record<WorkspaceKind, string> = {
  course: "Course",
  study_track: "Study Track",
  personal: "Personal",
  work: "Work",
  admin: "Admin",
};

export const TASK_KIND_LABELS: Record<TaskKind, string> = {
  assignment: "Assignment",
  study_session: "Study",
  admin: "Admin",
  bill: "Bill",
  errand: "Errand",
  work_task: "Work",
};

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
  scheduled: "Scheduled",
  paid: "Paid",
  snoozed: "Snoozed",
};

export const TASK_PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Low lift",
  medium: "Steady",
  high: "High",
  critical: "Critical",
};
