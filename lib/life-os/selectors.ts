import {
  addDays,
  differenceInCalendarDays,
  eachDayOfInterval,
  endOfDay,
  endOfWeek,
  format,
  isAfter,
  isBefore,
  isSameDay,
  isToday,
  parseISO,
  startOfDay,
} from "date-fns";

import type {
  AgendaDayGroup,
  DeadlineBucket,
  DeadlineBucketGroup,
  LifeItem,
  OverloadAssessment,
  TodayRecommendation,
  TodayRecommendationResult,
} from "@/lib/life-os/types";
import { DEADLINE_BUCKET_LABELS } from "@/lib/life-os/types";

const PRIORITY_WEIGHTS = {
  low: 8,
  medium: 18,
  high: 30,
  critical: 42,
} as const;

function getDueDate(item: LifeItem) {
  const source = item.dueAt ?? item.scheduledAt;
  return source ? parseISO(source) : undefined;
}

function getAgendaDate(item: LifeItem) {
  const source = item.scheduledAt ?? item.dueAt;
  return source ? parseISO(source) : undefined;
}

export function isComplete(item: LifeItem) {
  return item.status === "done" || item.status === "paid";
}

export function getIncompleteItems(items: LifeItem[]) {
  return items.filter((item) => !isComplete(item));
}

function compareByUrgency(a: LifeItem, b: LifeItem) {
  const aDate = getDueDate(a)?.getTime() ?? Number.MAX_SAFE_INTEGER;
  const bDate = getDueDate(b)?.getTime() ?? Number.MAX_SAFE_INTEGER;

  if (aDate !== bDate) {
    return aDate - bDate;
  }

  if (a.priority !== b.priority) {
    return PRIORITY_WEIGHTS[b.priority] - PRIORITY_WEIGHTS[a.priority];
  }

  return a.title.localeCompare(b.title);
}

export function getOverdueItems(items: LifeItem[], referenceDate = new Date()) {
  const today = startOfDay(referenceDate);

  return getIncompleteItems(items)
    .filter((item) => {
      const dueDate = getDueDate(item);

      return Boolean(dueDate && isBefore(dueDate, today));
    })
    .sort(compareByUrgency);
}

export function getTodayItems(items: LifeItem[], referenceDate = new Date()) {
  return getIncompleteItems(items)
    .filter((item) => {
      const dueDate = getDueDate(item);
      const agendaDate = getAgendaDate(item);

      return Boolean(
        (dueDate && isSameDay(dueDate, referenceDate)) ||
          (agendaDate && isSameDay(agendaDate, referenceDate)),
      );
    })
    .sort(compareByUrgency);
}

export function getTopPriorityItems(items: LifeItem[], limit = 5) {
  return getIncompleteItems(items)
    .sort((a, b) => {
      if (a.priority !== b.priority) {
        return PRIORITY_WEIGHTS[b.priority] - PRIORITY_WEIGHTS[a.priority];
      }

      return compareByUrgency(a, b);
    })
    .slice(0, limit);
}

export function getUpcomingDeadlines(
  items: LifeItem[],
  referenceDate = new Date(),
  limit = 6,
) {
  const start = startOfDay(referenceDate);
  const end = endOfDay(addDays(start, 7));

  return getIncompleteItems(items)
    .filter((item) => {
      const dueDate = getDueDate(item);

      return Boolean(
        dueDate &&
          !isBefore(dueDate, start) &&
          !isAfter(dueDate, end),
      );
    })
    .sort(compareByUrgency)
    .slice(0, limit);
}

export function groupItemsByAgendaDay(
  items: LifeItem[],
  referenceDate = new Date(),
): AgendaDayGroup[] {
  const start = startOfDay(referenceDate);
  const end = addDays(start, 7);
  const interval = eachDayOfInterval({ start, end });

  return interval.map((day) => ({
    key: format(day, "yyyy-MM-dd"),
    label: isToday(day) ? "Today" : format(day, "EEEE"),
    date: day,
    isToday: isToday(day),
    items: getIncompleteItems(items)
      .filter((item) => {
        const agendaDate = getAgendaDate(item);

        if (!agendaDate) {
          return false;
        }

        if (!isSameDay(agendaDate, day)) {
          return false;
        }

        return Boolean(
          item.scheduledAt || item.type === "appointment" || item.type === "reminder",
        );
      })
      .sort(compareByUrgency),
  }));
}

function getDeadlineBucket(item: LifeItem, referenceDate: Date): DeadlineBucket {
  const dueDate = getDueDate(item);
  const today = startOfDay(referenceDate);

  if (!dueDate) {
    return "later";
  }

  if (isBefore(dueDate, today)) {
    return "overdue";
  }

  if (isSameDay(dueDate, today)) {
    return "today";
  }

  const dayDiff = differenceInCalendarDays(dueDate, today);

  if (dayDiff <= 3) {
    return "next3Days";
  }

  if (isBefore(dueDate, endOfWeek(referenceDate, { weekStartsOn: 1 }))) {
    return "laterThisWeek";
  }

  return "later";
}

export function groupItemsByDeadlineBucket(
  items: LifeItem[],
  referenceDate = new Date(),
): DeadlineBucketGroup[] {
  const bucketOrder: DeadlineBucket[] = [
    "overdue",
    "today",
    "next3Days",
    "laterThisWeek",
    "later",
  ];

  return bucketOrder.map((bucket) => ({
    key: bucket,
    label: DEADLINE_BUCKET_LABELS[bucket],
    items: getIncompleteItems(items)
      .filter((item) => getDueDate(item) && getDeadlineBucket(item, referenceDate) === bucket)
      .sort(compareByUrgency),
  }));
}

export function getOverloadAssessment(
  items: LifeItem[],
  referenceDate = new Date(),
): OverloadAssessment {
  const overdueCount = getOverdueItems(items, referenceDate).length;
  const todayItems = getTodayItems(items, referenceDate);
  const todayHighPriorityCount = todayItems.filter((item) =>
    item.priority === "high" || item.priority === "critical",
  ).length;
  const todayEstimatedMinutes = todayItems.reduce(
    (sum, item) => sum + (item.estimatedMinutes ?? 0),
    0,
  );

  if (overdueCount >= 3) {
    return {
      isOverloaded: true,
      reason: `${overdueCount} overdue items are still tugging at today.`,
      suggestedAction: "Clear one overdue bill or admin task first to buy the rest of the day some air.",
    };
  }

  if (todayHighPriorityCount >= 4) {
    return {
      isOverloaded: true,
      reason: `${todayHighPriorityCount} high-stakes items landed on the same day.`,
      suggestedAction: "Choose one anchor task, then gently demote the rest into tomorrow's list.",
    };
  }

  if (todayEstimatedMinutes > 360) {
    return {
      isOverloaded: true,
      reason: `Today's visible load adds up to about ${todayEstimatedMinutes} minutes.`,
      suggestedAction: "Reschedule one medium-weight errand now so the evening still feels recoverable.",
    };
  }

  return {
    isOverloaded: false,
    reason: "Today's load looks steady and roomy.",
    suggestedAction: "Protect one focus block and let the rest stay flexible.",
  };
}

function buildRecommendationReason(item: LifeItem, referenceDate: Date) {
  const dueDate = getDueDate(item);
  const reasons: string[] = [];

  if (dueDate && isBefore(dueDate, startOfDay(referenceDate))) {
    reasons.push("it's already overdue");
  } else if (dueDate && isSameDay(dueDate, referenceDate)) {
    reasons.push("it's due today");
  } else if (item.scheduledAt && isSameDay(parseISO(item.scheduledAt), referenceDate)) {
    reasons.push("it's already on today's plan");
  }

  if ((item.estimatedMinutes ?? 0) > 0 && (item.estimatedMinutes ?? 0) <= 20) {
    reasons.push("it can be finished quickly");
  }

  if (item.type === "reminder" || item.type === "errand") {
    reasons.push("it fits a lower-energy window");
  }

  if (item.priority === "critical" || item.priority === "high") {
    reasons.push(`it's marked ${item.priority.replace("_", " ")}`);
  }

  return `Tackle this now because ${reasons.slice(0, 2).join(" and ")}.`;
}

export function scoreLifeItem(item: LifeItem, referenceDate = new Date()) {
  if (isComplete(item)) {
    return 0;
  }

  let score = PRIORITY_WEIGHTS[item.priority];
  const dueDate = getDueDate(item);

  if (dueDate && isBefore(dueDate, startOfDay(referenceDate))) {
    score += 45;
  }

  if (dueDate && isSameDay(dueDate, referenceDate)) {
    score += 25;
  }

  if (item.scheduledAt && isSameDay(parseISO(item.scheduledAt), referenceDate)) {
    score += 18;
  }

  if ((item.estimatedMinutes ?? 0) <= 20) {
    score += 12;
  } else if ((item.estimatedMinutes ?? 0) <= 45) {
    score += 6;
  }

  if ((item.type === "reminder" || item.type === "errand") && item.energy === "low") {
    score += 10;
  }

  return score;
}

export function getTodayRecommendations(
  items: LifeItem[],
  referenceDate = new Date(),
): TodayRecommendationResult {
  const ranked: TodayRecommendation[] = getIncompleteItems(items)
    .map((item) => ({
      item,
      score: scoreLifeItem(item, referenceDate),
      reason: buildRecommendationReason(item, referenceDate),
    }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => {
      if (a.score !== b.score) {
        return b.score - a.score;
      }

      return compareByUrgency(a.item, b.item);
    })
    .slice(0, 3);

  return {
    primary: ranked[0],
    secondary: ranked.slice(1),
  };
}

export function buildDailyNarrative(
  items: LifeItem[],
  referenceDate = new Date(),
) {
  const overdueCount = getOverdueItems(items, referenceDate).length;
  const todayCount = getTodayItems(items, referenceDate).length;
  const recommendations = getTodayRecommendations(items, referenceDate);
  const overload = getOverloadAssessment(items, referenceDate);

  if (overload.isOverloaded && recommendations.primary) {
    return `Today is fuller than it needs to be. Start with ${recommendations.primary.item.title.toLowerCase()}, then protect one quieter win before the rest of the list expands again.`;
  }

  if (todayCount === 0 && overdueCount === 0) {
    return "The board looks unusually calm. Use the open space for one meaningful future-facing task, then stop early on purpose.";
  }

  return `You have ${todayCount} active items in view${overdueCount ? ` and ${overdueCount} older loose ends` : ""}. A steady first move will matter more than trying to clear everything at once.`;
}
