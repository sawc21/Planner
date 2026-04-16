export const WORKSPACE_KINDS = ["course", "project"] as const;

export const TASK_KINDS = [
  "assignment",
  "study_session",
  "project_task",
  "admin",
  "bill",
  "errand",
] as const;

export const TASK_STATUSES = [
  "todo",
  "in_progress",
  "done",
  "scheduled",
  "paid",
  "snoozed",
] as const;

export const TASK_PRIORITIES = ["low", "medium", "high", "critical"] as const;
export const ENERGY_LEVELS = ["low", "medium", "high"] as const;

export const EVENT_KINDS = [
  "class",
  "office_hours",
  "meeting",
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

export const DASHBOARD_WIDGET_KINDS = [
  "primary_recommendation",
  "assistant_summary",
  "timeline",
  "school_overview",
  "active_projects",
  "urgent_deadlines",
  "quick_actions",
] as const;

export const PROJECT_MILESTONE_STATUSES = [
  "planned",
  "in_progress",
  "complete",
] as const;

export type WorkspaceKind = (typeof WORKSPACE_KINDS)[number];
export type TaskKind = (typeof TASK_KINDS)[number];
export type TaskStatus = (typeof TASK_STATUSES)[number];
export type TaskPriority = (typeof TASK_PRIORITIES)[number];
export type EnergyLevel = (typeof ENERGY_LEVELS)[number];
export type EventKind = (typeof EVENT_KINDS)[number];
export type MaterialKind = (typeof MATERIAL_KINDS)[number];
export type DashboardWidgetKind = (typeof DASHBOARD_WIDGET_KINDS)[number];
export type ProjectMilestoneStatus = (typeof PROJECT_MILESTONE_STATUSES)[number];

export type Workspace = {
  id: string;
  name: string;
  shortLabel: string;
  kind: WorkspaceKind;
  colorToken: string;
  icon: string;
  ownerLabel: string;
  progressSummary: string;
  active: boolean;
  creditHours?: number;
  currentGrade?: number;
  targetGrade?: number;
  semesterLabel?: string;
  projectHealth?: "green" | "watch" | "risk";
};

export type Task = {
  id: string;
  primaryWorkspaceId?: string;
  linkedWorkspaceIds: string[];
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
  workspaceId?: string;
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

export type ProjectMilestone = {
  id: string;
  workspaceId: string;
  title: string;
  summary: string;
  dueAt?: string;
  status: ProjectMilestoneStatus;
  progressPercent: number;
  linkedTaskIds?: string[];
};

export type DashboardWidget = {
  id: string;
  kind: DashboardWidgetKind;
  title: string;
  description: string;
  href: string;
  order: number;
  workspaceId?: string;
  accent: "violet" | "sky" | "amber" | "emerald" | "rose";
  layout: "hero" | "wide" | "compact";
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
  workspaceId?: string;
};

export type StudyPlan = {
  title: string;
  summary: string;
  steps: StudyPlanStep[];
};

export type TaskView = Task & {
  workspace?: Workspace;
  linkedWorkspaces: Workspace[];
};

export type EventView = Event & {
  workspace?: Workspace;
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
  openWindows: string[];
  loadPercent: number;
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

export type HomeWidgetData = {
  widget: DashboardWidget;
  headline: string;
  detail: string;
  stats: string[];
  accentLabel: string;
};

export type GradeWhatIfCard = {
  workspace: Workspace;
  currentGrade: number;
  targetGrade: number;
  nextItemTitle?: string;
  neededScore?: number;
  categoryLabel?: string;
};

export type AssistantReceipt = {
  title: string;
  lines: string[];
  href?: string;
};

export type AssistantResultCategory =
  | "Action"
  | "Plan"
  | "Dashboard Update"
  | "Priority Explanation"
  | "Navigation";

export type AssistantResultCard = {
  id: string;
  category: AssistantResultCategory;
  title: string;
  summary: string;
  lines: string[];
  href?: string;
  accent: "sky" | "violet" | "amber" | "emerald" | "rose";
};

export type HomeBriefingItem = {
  id: string;
  label: string;
  summary: string;
  href?: string;
};

export type TaskScope = "all" | "today" | "overdue" | "upcoming";

export type AssignmentFilterState = {
  query: string;
  workspaceId: string | "all";
  kind: TaskKind | "all";
  status: TaskStatus | "all";
  priority: TaskPriority | "all";
  scope: TaskScope;
};

export type AddTaskInput = {
  title: string;
  primaryWorkspaceId?: string;
  linkedWorkspaceIds?: string[];
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

export type CreateProjectMilestoneInput = {
  workspaceId: string;
  title: string;
  summary: string;
};

export type CommandIntent =
  | "add_task"
  | "add_event"
  | "add_material"
  | "build_dashboard"
  | "suggest_widgets"
  | "rebalance_schedule"
  | "focus_workspace"
  | "create_project"
  | "create_study_session"
  | "generate_weekly_plan"
  | "explain_priority"
  | "what_should_i_do_today"
  | "show_urgent_items";

export type CommandResult =
  | {
      intent: CommandIntent;
      kind: "mutation";
      message: string;
      receipt: AssistantReceipt;
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
      receipt?: AssistantReceipt;
    }
  | {
      intent: CommandIntent;
      kind: "recommendation";
      message: string;
      recommendation?: TodayRecommendation;
      receipt: AssistantReceipt;
    }
  | {
      intent: CommandIntent;
      kind: "plan";
      message: string;
      plan: StudyPlan;
      receipt: AssistantReceipt;
    }
  | {
      intent: CommandIntent;
      kind: "dashboard";
      message: string;
      widgets: DashboardWidget[];
      receipt: AssistantReceipt;
    }
  | {
      intent: CommandIntent;
      kind: "explanation";
      message: string;
      receipt: AssistantReceipt;
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
  milestones: ProjectMilestone[];
  widgets: DashboardWidget[];
  gradebooks: Gradebook[];
  constraintProfile: ConstraintProfile;
};

export const WORKSPACE_KIND_LABELS: Record<WorkspaceKind, string> = {
  course: "Course",
  project: "Project",
};

export const TASK_KIND_LABELS: Record<TaskKind, string> = {
  assignment: "Assignment",
  study_session: "Study session",
  project_task: "Project task",
  admin: "Admin",
  bill: "Bill",
  errand: "Errand",
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
