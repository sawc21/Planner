export const LIFE_ITEM_TYPES = [
  "task",
  "bill",
  "appointment",
  "reminder",
  "errand",
] as const;

export const LIFE_ITEM_STATUSES = [
  "todo",
  "in_progress",
  "done",
  "scheduled",
  "paid",
  "snoozed",
] as const;

export const LIFE_ITEM_PRIORITIES = [
  "low",
  "medium",
  "high",
  "critical",
] as const;

export const LIFE_ITEM_ENERGIES = ["low", "medium", "high"] as const;

export type LifeItemType = (typeof LIFE_ITEM_TYPES)[number];
export type LifeItemStatus = (typeof LIFE_ITEM_STATUSES)[number];
export type LifeItemPriority = (typeof LIFE_ITEM_PRIORITIES)[number];
export type LifeItemEnergy = (typeof LIFE_ITEM_ENERGIES)[number];

export type LifeItem = {
  id: string;
  type: LifeItemType;
  title: string;
  notes?: string;
  status: LifeItemStatus;
  priority: LifeItemPriority;
  dueAt?: string;
  scheduledAt?: string;
  completedAt?: string;
  category: string;
  tags: string[];
  location?: string;
  amount?: number;
  estimatedMinutes?: number;
  energy: LifeItemEnergy;
  recurring?: boolean;
};

export type DeadlineBucket =
  | "overdue"
  | "today"
  | "next3Days"
  | "laterThisWeek"
  | "later";

export type AgendaDayGroup = {
  key: string;
  label: string;
  date: Date;
  isToday: boolean;
  items: LifeItem[];
};

export type DeadlineBucketGroup = {
  key: DeadlineBucket;
  label: string;
  items: LifeItem[];
};

export type TodayRecommendation = {
  item: LifeItem;
  score: number;
  reason: string;
};

export type TodayRecommendationResult = {
  primary?: TodayRecommendation;
  secondary: TodayRecommendation[];
};

export type OverloadAssessment = {
  isOverloaded: boolean;
  reason: string;
  suggestedAction: string;
};

export type TaskShortcut = "all" | "today" | "overdue" | "upcoming";

export type TaskFilterState = {
  query: string;
  type: LifeItemType | "all";
  status: LifeItemStatus | "all";
  priority: LifeItemPriority | "all";
  shortcut: TaskShortcut;
};

export const TYPE_LABELS: Record<LifeItemType, string> = {
  task: "Task",
  bill: "Bill",
  appointment: "Appointment",
  reminder: "Reminder",
  errand: "Errand",
};

export const PRIORITY_LABELS: Record<LifeItemPriority, string> = {
  low: "Low lift",
  medium: "Steady",
  high: "High",
  critical: "Critical",
};

export const STATUS_LABELS: Record<LifeItemStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
  scheduled: "Scheduled",
  paid: "Paid",
  snoozed: "Snoozed",
};

export const DEADLINE_BUCKET_LABELS: Record<DeadlineBucket, string> = {
  overdue: "Overdue",
  today: "Due today",
  next3Days: "Next 3 days",
  laterThisWeek: "Later this week",
  later: "Later",
};
