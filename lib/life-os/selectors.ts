import {
  addDays,
  differenceInCalendarDays,
  eachDayOfInterval,
  endOfDay,
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
  AgendaEntry,
  ConstraintProfile,
  Event,
  EventView,
  Gradebook,
  LifeOsSnapshot,
  OverloadAssessment,
  ProgressCard,
  ProgressRecord,
  StudyBuddyInsight,
  StudyPlan,
  StudyPlanStep,
  Task,
  TaskView,
  TodayRecommendation,
  TodayRecommendationResult,
  Workspace,
  WorkspaceRisk,
} from "@/lib/life-os/types";

const PRIORITY_WEIGHTS = {
  low: 8,
  medium: 18,
  high: 32,
  critical: 46,
} as const;

type ScoreSignal = {
  label: string;
  summary: string;
  value: number;
};

function getTaskDate(task: Task) {
  const source = task.scheduledAt ?? task.dueAt;
  return source ? parseISO(source) : undefined;
}

function getWorkspaceById(workspaces: Workspace[], workspaceId: string) {
  return workspaces.find((workspace) => workspace.id === workspaceId);
}

function attachTaskWorkspace(tasks: Task[], workspaces: Workspace[]) {
  return tasks
    .map((task) => {
      const workspace = getWorkspaceById(workspaces, task.workspaceId);
      return workspace ? ({ ...task, workspace } satisfies TaskView) : undefined;
    })
    .filter((task): task is TaskView => Boolean(task));
}

function attachEventWorkspace(events: Event[], workspaces: Workspace[]) {
  return events
    .map((event) => {
      const workspace = getWorkspaceById(workspaces, event.workspaceId);
      return workspace ? ({ ...event, workspace } satisfies EventView) : undefined;
    })
    .filter((event): event is EventView => Boolean(event));
}

function compareTasksByUrgency(a: TaskView, b: TaskView) {
  const aDate = getTaskDate(a)?.getTime() ?? Number.MAX_SAFE_INTEGER;
  const bDate = getTaskDate(b)?.getTime() ?? Number.MAX_SAFE_INTEGER;

  if (aDate !== bDate) {
    return aDate - bDate;
  }

  if (a.priority !== b.priority) {
    return PRIORITY_WEIGHTS[b.priority] - PRIORITY_WEIGHTS[a.priority];
  }

  return a.title.localeCompare(b.title);
}

function compareAgendaEntry(a: AgendaEntry, b: AgendaEntry) {
  return parseISO(a.timestamp).getTime() - parseISO(b.timestamp).getTime();
}

function isTaskComplete(task: Task) {
  return task.status === "done" || task.status === "paid";
}

function buildSignals(
  task: TaskView,
  constraints: ConstraintProfile,
  referenceDate: Date,
): ScoreSignal[] {
  const signals: ScoreSignal[] = [];
  const taskDate = getTaskDate(task);

  signals.push({
    label: `${task.priority[0].toUpperCase()}${task.priority.slice(1)} priority +${PRIORITY_WEIGHTS[task.priority]}`,
    summary: `${task.priority} priority`,
    value: PRIORITY_WEIGHTS[task.priority],
  });

  if (taskDate && isBefore(taskDate, startOfDay(referenceDate))) {
    signals.push({
      label: "Overdue +45",
      summary: "it is overdue",
      value: 45,
    });
  }

  if (taskDate && isSameDay(taskDate, referenceDate)) {
    signals.push({
      label: "Today +24",
      summary: "it lands today",
      value: 24,
    });
  }

  if (task.workspace.kind === "course" && task.workspace.currentGrade != null && task.workspace.currentGrade < 85) {
    signals.push({
      label: "Grade risk +16",
      summary: "its course grade is under pressure",
      value: 16,
    });
  }

  if (task.workspace.kind === "study_track") {
    signals.push({
      label: "Momentum +10",
      summary: "it keeps a study track moving",
      value: 10,
    });
  }

  if ((task.estimatedMinutes ?? 0) > 0 && (task.estimatedMinutes ?? 0) <= 25) {
    signals.push({
      label: "Quick win +14",
      summary: "it is short enough to close quickly",
      value: 14,
    });
  } else if ((task.estimatedMinutes ?? 0) <= 60) {
    signals.push({
      label: "One sitting +7",
      summary: "it fits one concentrated block",
      value: 7,
    });
  }

  if (
    task.energy === "low" &&
    (constraints.defaultEnergyProfile === "low" || constraints.hoursRemainingThisWeek <= 6)
  ) {
    signals.push({
      label: "Energy fit +10",
      summary: "it fits your available energy",
      value: 10,
    });
  }

  if (task.kind === "bill" && task.amount != null && task.amount <= constraints.budgetRemainingThisWeek) {
    signals.push({
      label: "Budget-clearable +8",
      summary: "the remaining budget can absorb it",
      value: 8,
    });
  }

  if (task.status === "in_progress") {
    signals.push({
      label: "Momentum +9",
      summary: "you already have momentum on it",
      value: 9,
    });
  }

  return signals.sort((a, b) => b.value - a.value);
}

function buildExplanation(signals: ScoreSignal[]) {
  const summaries = signals.slice(0, 3).map((signal) => signal.summary);
  return summaries.length
    ? `Chosen because ${summaries.join(", ")}.`
    : "Chosen because it gives the day the clearest shape.";
}

function buildReason(signals: ScoreSignal[]) {
  const summaries = signals.slice(0, 2).map((signal) => signal.summary);
  return summaries.length
    ? `Start here because ${summaries.join(" and ")}.`
    : "Start here because it offers the cleanest next move.";
}

function calculateGradeRiskScore(gradebook: Gradebook | undefined) {
  if (!gradebook) {
    return 0;
  }

  const gap = gradebook.targetGrade - gradebook.currentGrade;
  return gap > 0 ? gap * 2 : 0;
}

function calculateProgressRiskScore(record: ProgressRecord) {
  const ratio = record.currentValue / Math.max(record.targetValue, 1);
  const dueSoon = record.dueAt
    ? differenceInCalendarDays(parseISO(record.dueAt), new Date()) <= 7
    : false;

  return (ratio < 0.7 ? 18 : 8) + (dueSoon ? 8 : 0);
}

export function getTaskViews(data: Pick<LifeOsSnapshot, "tasks" | "workspaces">) {
  return attachTaskWorkspace(data.tasks, data.workspaces);
}

export function getEventViews(data: Pick<LifeOsSnapshot, "events" | "workspaces">) {
  return attachEventWorkspace(data.events, data.workspaces);
}

export function getIncompleteTasks(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces">,
) {
  return getTaskViews(data).filter((task) => !isTaskComplete(task));
}

export function getOverdueTasks(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces">,
  referenceDate = new Date(),
) {
  const today = startOfDay(referenceDate);

  return getIncompleteTasks(data)
    .filter((task) => {
      const taskDate = getTaskDate(task);
      return Boolean(taskDate && isBefore(taskDate, today));
    })
    .sort(compareTasksByUrgency);
}

export function getTodayTasks(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces">,
  referenceDate = new Date(),
) {
  return getIncompleteTasks(data)
    .filter((task) => {
      const taskDate = getTaskDate(task);
      return Boolean(taskDate && isSameDay(taskDate, referenceDate));
    })
    .sort(compareTasksByUrgency);
}

export function getUpcomingTasks(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces">,
  referenceDate = new Date(),
  limit = 6,
) {
  const start = startOfDay(referenceDate);
  const end = endOfDay(addDays(start, 7));

  return getIncompleteTasks(data)
    .filter((task) => {
      const taskDate = getTaskDate(task);
      return Boolean(taskDate && !isBefore(taskDate, start) && !isAfter(taskDate, end));
    })
    .sort(compareTasksByUrgency)
    .slice(0, limit);
}

export function getTodayRecommendations(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces" | "constraintProfile">,
  referenceDate = new Date(),
): TodayRecommendationResult {
  const ranked = getIncompleteTasks(data)
    .map((task) => {
      const signals = buildSignals(task, data.constraintProfile, referenceDate);
      const score = signals.reduce((sum, signal) => sum + signal.value, 0);

      return {
        item: task,
        score,
        reason: buildReason(signals),
        explanation: buildExplanation(signals),
        scoreBreakdown: signals.map((signal) => signal.label).slice(0, 4),
      } satisfies TodayRecommendation;
    })
    .filter((entry) => entry.score > 0)
    .sort((a, b) => {
      if (a.score !== b.score) {
        return b.score - a.score;
      }

      return compareTasksByUrgency(a.item, b.item);
    })
    .slice(0, 3);

  return {
    primary: ranked[0],
    secondary: ranked.slice(1),
  };
}

export function getOverloadAssessment(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces" | "constraintProfile">,
  referenceDate = new Date(),
): OverloadAssessment {
  const overdueCount = getOverdueTasks(data, referenceDate).length;
  const todayTasks = getTodayTasks(data, referenceDate);
  const highPriorityCount = todayTasks.filter(
    (task) => task.priority === "high" || task.priority === "critical",
  ).length;
  const todayMinutes = todayTasks.reduce((sum, task) => sum + (task.estimatedMinutes ?? 0), 0);
  const hoursPressure = todayMinutes > data.constraintProfile.hoursRemainingThisWeek * 60;

  if (overdueCount >= 3 || highPriorityCount >= 4 || hoursPressure) {
    return {
      isOverloaded: true,
      severity: "overloaded",
      reason:
        overdueCount >= 3
          ? `${overdueCount} overdue tasks are still pulling on the week.`
          : highPriorityCount >= 4
            ? `${highPriorityCount} high-stakes tasks are stacked onto the same day.`
            : `Today's visible work is heavier than the ${data.constraintProfile.hoursRemainingThisWeek} hours left in the week budget.`,
      suggestedAction:
        "Finish one overdue or short task first, then move one medium-weight item before the day starts widening.",
    };
  }

  if (overdueCount >= 2 || highPriorityCount >= 3 || todayMinutes > 240) {
    return {
      isOverloaded: false,
      severity: "watch",
      reason: "The board is still manageable, but one extra commitment could tip it.",
      suggestedAction:
        "Protect one anchor task and keep tonight's study flow narrower than usual.",
    };
  }

  return {
    isOverloaded: false,
    severity: "calm",
    reason: "The current mix of work, study, and life admin still looks workable.",
    suggestedAction: "Use the open room to close one meaningful task before expanding the plan.",
  };
}

export function getAgendaGroups(
  data: Pick<LifeOsSnapshot, "tasks" | "events" | "workspaces">,
  referenceDate = new Date(),
): AgendaDayGroup[] {
  const start = startOfDay(referenceDate);
  const end = addDays(start, 6);
  const days = eachDayOfInterval({ start, end });
  const taskViews = getIncompleteTasks(data);
  const eventViews = getEventViews(data);

  return days.map((day) => {
    const taskEntries: AgendaEntry[] = taskViews
      .filter((task) => {
        const taskDate = getTaskDate(task);
        return Boolean(taskDate && isSameDay(taskDate, day));
      })
      .map((task) => ({
        id: `task-${task.id}`,
        kind: "task",
        timestamp: task.scheduledAt ?? task.dueAt ?? new Date().toISOString(),
        task,
      }));

    const eventEntries: AgendaEntry[] = eventViews
      .filter((event) => isSameDay(parseISO(event.startAt), day))
      .map((event) => ({
        id: `event-${event.id}`,
        kind: "event",
        timestamp: event.startAt,
        event,
      }));

    const entries = [...taskEntries, ...eventEntries].sort(compareAgendaEntry);
    const pressureCount = entries.filter((entry) =>
      entry.kind === "task"
        ? entry.task?.priority === "high" || entry.task?.priority === "critical"
        : entry.event?.priority === "high" || entry.event?.priority === "critical",
    ).length;

    return {
      key: format(day, "yyyy-MM-dd"),
      label: isToday(day) ? "Today" : format(day, "EEEE"),
      date: day,
      isToday: isToday(day),
      pressureLabel:
        pressureCount >= 3
          ? "Heavy pressure"
          : pressureCount === 2
            ? "Busy"
            : entries.length
              ? "Manageable"
              : "Open",
      entries,
    };
  });
}

export function getAtRiskWorkspaces(
  data: Pick<
    LifeOsSnapshot,
    "workspaces" | "tasks" | "gradebooks" | "progressRecords"
  >,
  referenceDate = new Date(),
  limit = 4,
) {
  const taskViews = getIncompleteTasks(data);

  return data.workspaces
    .map((workspace) => {
      const workspaceTasks = taskViews.filter((task) => task.workspaceId === workspace.id);
      const overdueTasks = workspaceTasks.filter((task) => {
        const taskDate = getTaskDate(task);
        return Boolean(taskDate && isBefore(taskDate, startOfDay(referenceDate)));
      }).length;
      const upcomingCritical = workspaceTasks.filter(
        (task) =>
          (task.priority === "critical" || task.priority === "high") &&
          (() => {
            const taskDate = getTaskDate(task);
            return Boolean(taskDate && differenceInCalendarDays(taskDate, referenceDate) <= 2);
          })(),
      ).length;
      const gradebook = data.gradebooks.find((entry) => entry.workspaceId === workspace.id);
      const progress = data.progressRecords.filter((record) => record.workspaceId === workspace.id);
      const progressRisk = progress.reduce(
        (sum, record) => sum + calculateProgressRiskScore(record),
        0,
      );
      const gradeRisk = calculateGradeRiskScore(gradebook);
      const score = overdueTasks * 18 + upcomingCritical * 14 + gradeRisk + progressRisk;
      const signals = [
        overdueTasks ? `${overdueTasks} overdue` : undefined,
        upcomingCritical ? `${upcomingCritical} urgent` : undefined,
        gradeRisk ? `${workspace.currentGrade}% grade` : undefined,
        progressRisk ? "progress slipping" : undefined,
      ].filter(Boolean) as string[];

      return {
        workspace,
        score,
        reason:
          signals.length > 0
            ? `${workspace.shortLabel} is carrying ${signals.join(", ")}.`
            : `${workspace.shortLabel} is currently stable.`,
        signals,
      } satisfies WorkspaceRisk;
    })
    .filter((risk) => risk.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

export function getWorkspaceBundle(
  data: LifeOsSnapshot,
  workspaceId: string,
) {
  const workspace = data.workspaces.find((entry) => entry.id === workspaceId);

  if (!workspace) {
    return undefined;
  }

  return {
    workspace,
    tasks: getTaskViews(data)
      .filter((task) => task.workspaceId === workspaceId)
      .sort(compareTasksByUrgency),
    events: getEventViews(data)
      .filter((event) => event.workspaceId === workspaceId)
      .sort((a, b) => parseISO(a.startAt).getTime() - parseISO(b.startAt).getTime()),
    materials: data.materials.filter((material) => material.workspaceId === workspaceId),
    gradebook: data.gradebooks.find((entry) => entry.workspaceId === workspaceId),
    progress: data.progressRecords.filter((entry) => entry.workspaceId === workspaceId),
  };
}

export function getConstraintAwarePlan(
  data: Pick<
    LifeOsSnapshot,
    "tasks" | "workspaces" | "constraintProfile" | "gradebooks" | "progressRecords"
  >,
  workspaceId?: string,
  referenceDate = new Date(),
): StudyPlan {
  const taskPool = workspaceId
    ? getIncompleteTasks(data).filter((task) => task.workspaceId === workspaceId)
    : getIncompleteTasks(data);
  const recommendations = getTodayRecommendations(data, referenceDate);
  const preferredTasks =
    taskPool.length > 0
      ? taskPool.sort(compareTasksByUrgency).slice(0, 3)
      : recommendations.primary
        ? [recommendations.primary.item, ...recommendations.secondary.map((entry) => entry.item)]
        : [];

  const availableMinutes = data.constraintProfile.hoursRemainingThisWeek * 60;
  let consumed = 0;

  const steps: StudyPlanStep[] = preferredTasks.map((task) => {
    const minutes = Math.min(task.estimatedMinutes ?? 30, Math.max(20, availableMinutes - consumed));
    consumed += minutes;

    return {
      id: `${task.id}-step`,
      title: task.title,
      reason:
        task.workspace.kind === "course"
          ? "It moves a graded or time-sensitive academic commitment."
          : task.workspace.kind === "study_track"
            ? "It keeps momentum in a structured learning flow."
            : "It reduces admin drag and buys room for the rest of the week.",
      minutes,
      workspaceId: task.workspaceId,
    };
  });

  return {
    title: workspaceId ? "Focused study flow" : "Constraint-aware plan",
    summary:
      workspaceId
        ? `This flow respects the remaining ${data.constraintProfile.hoursRemainingThisWeek} hours while keeping the selected workspace moving.`
        : `This plan balances study, life admin, and work against the ${data.constraintProfile.hoursRemainingThisWeek} hours and $${data.constraintProfile.budgetRemainingThisWeek} still available this week.`,
    steps,
  };
}

export function getBuddyInsight(
  data: Pick<
    LifeOsSnapshot,
    "tasks" | "workspaces" | "constraintProfile" | "gradebooks" | "progressRecords"
  >,
  workspaceId?: string,
  referenceDate = new Date(),
): StudyBuddyInsight {
  const atRisk = getAtRiskWorkspaces(data, referenceDate, 1)[0];
  const recommendation = getTodayRecommendations(data, referenceDate).primary;

  if (workspaceId) {
    const bundle = getWorkspaceBundle(data as LifeOsSnapshot, workspaceId);

    if (!bundle) {
      return {
        title: "Planning Buddy",
        summary: "This workspace does not have enough context yet.",
        bullets: ["Add one task or material to give the workspace shape."],
        actionLabel: "Open workspaces",
        actionHref: "/workspaces",
      };
    }

    return {
      title:
        bundle.workspace.kind === "course" ? "Study Buddy" : "Planning Buddy",
      summary:
        bundle.workspace.kind === "course"
          ? `${bundle.workspace.shortLabel} needs a tighter sequence between assignments, class time, and grade pressure.`
          : `${bundle.workspace.shortLabel} will move best with one narrow session instead of a long catch-up block.`,
      bullets: [
        bundle.tasks[0]
          ? `Open with ${bundle.tasks[0].title.toLowerCase()}.`
          : "Start by adding one concrete task to this workspace.",
        bundle.materials[0]
          ? `Use ${bundle.materials[0].title.toLowerCase()} as the source material.`
          : "Add one material summary so the workspace has context to plan against.",
        bundle.gradebook
          ? `Protect the grade floor while aiming for ${bundle.gradebook.targetGrade}%.`
          : "Keep progress moving with shorter, repeatable sessions.",
      ],
      actionLabel: "See full plan",
      actionHref: "/command",
    };
  }

  return {
    title: "Planning Buddy",
    summary:
      atRisk && recommendation
        ? `${atRisk.workspace.shortLabel} is the most exposed workspace, and ${recommendation.item.title.toLowerCase()} is the cleanest place to relieve pressure.`
        : "The board is steady enough to keep the next move simple.",
    bullets: [
      recommendation
        ? `Start with ${recommendation.item.title.toLowerCase()}.`
        : "Use one short task as your anchor.",
      atRisk
        ? `Watch ${atRisk.workspace.name.toLowerCase()} next.`
        : "No workspace is clearly slipping right now.",
      `You still have ${data.constraintProfile.hoursRemainingThisWeek} hours and $${data.constraintProfile.budgetRemainingThisWeek} to plan around this week.`,
    ],
    actionLabel: "Build study flow",
    actionHref: "/command",
  };
}

export function buildDailyNarrative(
  data: Pick<
    LifeOsSnapshot,
    "tasks" | "workspaces" | "constraintProfile" | "gradebooks" | "progressRecords"
  >,
  referenceDate = new Date(),
) {
  const recommendation = getTodayRecommendations(data, referenceDate).primary;
  const overload = getOverloadAssessment(data, referenceDate);
  const atRisk = getAtRiskWorkspaces(data, referenceDate, 1)[0];

  if (recommendation && overload.severity === "overloaded") {
    return `The board is carrying more than today's margin can comfortably hold. Start with ${recommendation.item.title.toLowerCase()}, then deliberately narrow the rest of the plan.`;
  }

  if (recommendation && atRisk) {
    return `${atRisk.workspace.shortLabel} needs the most attention, and ${recommendation.item.title.toLowerCase()} is the cleanest way to make progress without widening the day.`;
  }

  if (recommendation) {
    return `The day is still workable. Let ${recommendation.item.title.toLowerCase()} set the pace before you expand the plan.`;
  }

  return "Nothing urgent is pressing right now. Use the space for one future-facing task, then stop early on purpose.";
}

export function getProgressCards(
  data: Pick<
    LifeOsSnapshot,
    "workspaces" | "gradebooks" | "progressRecords" | "tasks"
  >,
) {
  const taskViews = getTaskViews(data);

  const courseCards = data.gradebooks.flatMap((gradebook) => {
    const workspace = data.workspaces.find((entry) => entry.id === gradebook.workspaceId);
    if (!workspace) {
      return [];
    }

    const nextPlanned = gradebook.items.find((item) => item.status === "planned");
    const neededOnNext = nextPlanned
      ? Math.min(
          100,
          Math.max(
            0,
            Math.round(
              gradebook.targetGrade + (gradebook.targetGrade - gradebook.currentGrade) * 1.5,
            ),
          ),
        )
      : undefined;

    return [{
      workspace,
      title: `${gradebook.currentGrade}% current grade`,
      detail: nextPlanned
        ? `${nextPlanned.title} is the next grade-moving item.`
        : "No planned grade items are visible right now.",
      currentValue: gradebook.currentGrade,
      targetValue: gradebook.targetGrade,
      neededOnNext,
    } satisfies ProgressCard];
  });

  const trackCards = data.progressRecords.flatMap((record) => {
    const workspace = data.workspaces.find((entry) => entry.id === record.workspaceId);
    if (!workspace) {
      return [];
    }

    return [{
      workspace,
      title: `${record.currentValue}/${record.targetValue} ${record.unit}`,
      detail:
        record.confidence === "low"
          ? "Confidence is slipping enough that a shorter, more frequent plan would help."
          : "Momentum is still acceptable, but the track benefits from consistency.",
      currentValue: record.currentValue,
      targetValue: record.targetValue,
    } satisfies ProgressCard];
  });

  const lifeCards: ProgressCard[] = data.workspaces
    .filter((workspace) => workspace.kind === "personal" || workspace.kind === "work" || workspace.kind === "admin")
    .map((workspace) => {
      const workspaceTasks = taskViews.filter((task) => task.workspaceId === workspace.id);
      const completedCount = workspaceTasks.filter((task) => isTaskComplete(task)).length;

      return {
        workspace,
        title: `${completedCount}/${workspaceTasks.length || 1} tasks complete`,
        detail: workspace.progressSummary,
        currentValue: completedCount,
        targetValue: workspaceTasks.length || undefined,
      } satisfies ProgressCard;
    });

  return {
    courseCards,
    trackCards,
    lifeCards,
  } as {
    courseCards: ProgressCard[];
    trackCards: ProgressCard[];
    lifeCards: ProgressCard[];
  };
}
