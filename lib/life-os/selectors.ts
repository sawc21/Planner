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
  set,
  startOfDay,
  startOfWeek,
} from "date-fns";

import type {
  ActiveWeeklyPlan,
  AgendaDayGroup,
  AgendaEntry,
  AssistantActivityEvent,
  AssistantActivitySurface,
  AssistantResultCard,
  AssistantReceipt,
  CommandResult,
  ConstraintProfile,
  DashboardWidget,
  Event,
  EventView,
  GradeWhatIfCard,
  HomeWidgetData,
  HomeBriefingItem,
  LifeOsSnapshot,
  OverloadAssessment,
  PlannedStep,
  ProgressCard,
  ProjectMilestone,
  ScheduleSuggestion,
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

const FALLBACK_WORKSPACE: Workspace = {
  id: "general",
  name: "Independent",
  shortLabel: "GENERAL",
  kind: "project",
  colorToken: "bg-stone-200 text-stone-950",
  icon: "folder-open",
  ownerLabel: "Orbit OS",
  progressSummary: "Independent work that is not tied to a specific workspace.",
  active: true,
  projectHealth: "watch",
};

type ScoreSignal = {
  label: string;
  summary: string;
  value: number;
};

function getTaskDate(task: Task) {
  const source = task.scheduledAt ?? task.dueAt;
  return source ? parseISO(source) : undefined;
}

function getWorkspaceById(workspaces: Workspace[], workspaceId?: string) {
  if (!workspaceId) {
    return undefined;
  }

  return workspaces.find((workspace) => workspace.id === workspaceId);
}

function taskTouchesWorkspace(task: Task, workspaceId: string) {
  return (
    task.primaryWorkspaceId === workspaceId ||
    task.linkedWorkspaceIds.includes(workspaceId)
  );
}

function attachTaskWorkspaces(tasks: Task[], workspaces: Workspace[]) {
  return tasks.map((task) => {
    const workspace =
      getWorkspaceById(workspaces, task.primaryWorkspaceId) ??
      getWorkspaceById(workspaces, task.linkedWorkspaceIds[0]) ??
      FALLBACK_WORKSPACE;
    const linkedWorkspaces = [
      ...new Map(
        [task.primaryWorkspaceId, ...task.linkedWorkspaceIds]
          .map((workspaceId) => getWorkspaceById(workspaces, workspaceId))
          .filter((entry): entry is Workspace => Boolean(entry))
          .map((resolvedWorkspace) => [resolvedWorkspace.id, resolvedWorkspace]),
      ).values(),
    ];

    return { ...task, workspace, linkedWorkspaces } satisfies TaskView;
  });
}

function attachEventWorkspace(events: Event[], workspaces: Workspace[]) {
  return events.map((event) => ({
    ...event,
    workspace: getWorkspaceById(workspaces, event.workspaceId) ?? FALLBACK_WORKSPACE,
  })) satisfies EventView[];
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
  const workspace = task.workspace ?? FALLBACK_WORKSPACE;

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

  if (workspace.kind === "course" && workspace.currentGrade != null && workspace.currentGrade < 87) {
    signals.push({
      label: "Grade risk +16",
      summary: "its course grade is under pressure",
      value: 16,
    });
  }

  if (workspace.kind === "project" && workspace.projectHealth === "risk") {
    signals.push({
      label: "Project health +12",
      summary: "its project is slipping",
      value: 12,
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

function compareAgendaEntry(a: AgendaEntry, b: AgendaEntry) {
  return parseISO(a.timestamp).getTime() - parseISO(b.timestamp).getTime();
}

function calculateCourseRisk(
  workspace: Workspace,
  tasks: TaskView[],
  data: Pick<LifeOsSnapshot, "gradebooks">,
  referenceDate: Date,
) {
  const overdueTasks = tasks.filter((task) => {
    const taskDate = getTaskDate(task);
    return Boolean(taskDate && isBefore(taskDate, startOfDay(referenceDate)));
  }).length;
  const highUrgency = tasks.filter((task) => {
    const taskDate = getTaskDate(task);
    return Boolean(
      taskDate &&
        differenceInCalendarDays(taskDate, referenceDate) <= 2 &&
        (task.priority === "critical" || task.priority === "high"),
    );
  }).length;
  const gradebook = data.gradebooks.find((entry) => entry.workspaceId === workspace.id);
  const gradeRisk =
    gradebook && gradebook.targetGrade > gradebook.currentGrade
      ? (gradebook.targetGrade - gradebook.currentGrade) * 2
      : 0;

  return {
    score: overdueTasks * 18 + highUrgency * 14 + gradeRisk,
    signals: [
      overdueTasks ? `${overdueTasks} overdue` : undefined,
      highUrgency ? `${highUrgency} urgent` : undefined,
      gradeRisk ? `${workspace.currentGrade}% grade` : undefined,
    ].filter(Boolean) as string[],
  };
}

function calculateProjectRisk(
  workspace: Workspace,
  tasks: TaskView[],
  milestones: ProjectMilestone[],
  referenceDate: Date,
) {
  const overdueTasks = tasks.filter((task) => {
    const taskDate = getTaskDate(task);
    return Boolean(taskDate && isBefore(taskDate, startOfDay(referenceDate)));
  }).length;
  const milestoneRisk = milestones
    .filter((milestone) => milestone.workspaceId === workspace.id)
    .reduce((sum, milestone) => {
      const dueSoon = milestone.dueAt
        ? differenceInCalendarDays(parseISO(milestone.dueAt), referenceDate) <= 3
        : false;
      return sum + (milestone.status !== "complete" && dueSoon ? 20 : 0);
    }, 0);
  const healthRisk =
    workspace.projectHealth === "risk" ? 18 : workspace.projectHealth === "watch" ? 8 : 0;

  return {
    score: overdueTasks * 16 + milestoneRisk + healthRisk,
    signals: [
      overdueTasks ? `${overdueTasks} overdue` : undefined,
      milestoneRisk ? "milestone due soon" : undefined,
      workspace.projectHealth === "risk" ? "project health at risk" : undefined,
    ].filter(Boolean) as string[],
  };
}

export function getTaskViews(data: Pick<LifeOsSnapshot, "tasks" | "workspaces">) {
  return attachTaskWorkspaces(data.tasks, data.workspaces);
}

export function getEventViews(data: Pick<LifeOsSnapshot, "events" | "workspaces">) {
  return attachEventWorkspace(data.events, data.workspaces);
}

export function getIncompleteTasks(data: Pick<LifeOsSnapshot, "tasks" | "workspaces">) {
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
  limit = 8,
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

export function getUrgentDeadlines(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces">,
  referenceDate = new Date(),
  limit = 6,
) {
  return [...getOverdueTasks(data, referenceDate), ...getTodayTasks(data, referenceDate)]
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

  if (overdueCount >= 3 || highPriorityCount >= 4 || todayMinutes > 360) {
    return {
      isOverloaded: true,
      severity: "overloaded",
      reason:
        overdueCount >= 3
          ? `${overdueCount} overdue commitments are still pulling on the week.`
          : highPriorityCount >= 4
            ? `${highPriorityCount} high-stakes items are stacked on the same day.`
            : `Today's visible load is heavier than a 6-hour study-and-work margin.`,
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
    reason: "The current mix of school, projects, and life admin still looks workable.",
    suggestedAction: "Use the open room to close one meaningful task before expanding the plan.",
  };
}

export function getAgendaGroups(
  data: Pick<LifeOsSnapshot, "tasks" | "events" | "workspaces">,
  referenceDate = new Date(),
): AgendaDayGroup[] {
  const start = startOfWeek(referenceDate, { weekStartsOn: 1 });
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
    const totalMinutes = entries.reduce((sum, entry) => {
      if (entry.kind === "task" && entry.task) {
        return sum + (entry.task.estimatedMinutes ?? 45);
      }

      if (entry.event?.endAt) {
        const minutes =
          (parseISO(entry.event.endAt).getTime() - parseISO(entry.event.startAt).getTime()) /
          60000;
        return sum + minutes;
      }

      return sum + 60;
    }, 0);
    const pressureCount = entries.filter((entry) =>
      entry.kind === "task"
        ? entry.task?.priority === "high" || entry.task?.priority === "critical"
        : entry.event?.priority === "high" || entry.event?.priority === "critical",
    ).length;
    const openWindows: string[] = [];

    if (totalMinutes < 240) {
      openWindows.push("Late afternoon open");
    }
    if (totalMinutes < 360) {
      openWindows.push("Evening block available");
    }
    if (!entries.length) {
      openWindows.push("Wide-open day");
    }

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
      openWindows,
      loadPercent: Math.min(100, Math.round((totalMinutes / 480) * 100)),
    };
  });
}

export function getAtRiskWorkspaces(
  data: Pick<LifeOsSnapshot, "workspaces" | "tasks" | "gradebooks" | "milestones">,
  referenceDate = new Date(),
  limit = 4,
) {
  const taskViews = getIncompleteTasks(data);

  return data.workspaces
    .map((workspace) => {
      const workspaceTasks = taskViews.filter((task) => taskTouchesWorkspace(task, workspace.id));
      const risk =
        workspace.kind === "course"
          ? calculateCourseRisk(workspace, workspaceTasks, data, referenceDate)
          : calculateProjectRisk(workspace, workspaceTasks, data.milestones, referenceDate);

      return {
        workspace,
        score: risk.score,
        reason:
          risk.signals.length > 0
            ? `${workspace.shortLabel} is carrying ${risk.signals.join(", ")}.`
            : `${workspace.shortLabel} is currently stable.`,
        signals: risk.signals,
      } satisfies WorkspaceRisk;
    })
    .filter((risk) => risk.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

export function getWorkspaceBundle(data: LifeOsSnapshot, workspaceId: string) {
  const workspace = data.workspaces.find((entry) => entry.id === workspaceId);

  if (!workspace) {
    return undefined;
  }

  return {
    workspace,
    tasks: getTaskViews(data)
      .filter((task) => taskTouchesWorkspace(task, workspaceId))
      .sort(compareTasksByUrgency),
    events: getEventViews(data)
      .filter((event) => event.workspace?.id === workspaceId)
      .sort((a, b) => parseISO(a.startAt).getTime() - parseISO(b.startAt).getTime()),
    materials: data.materials.filter((material) => material.workspaceId === workspaceId),
    milestones: data.milestones.filter((milestone) => milestone.workspaceId === workspaceId),
    gradebook: data.gradebooks.find((entry) => entry.workspaceId === workspaceId),
  };
}

export function getConstraintAwarePlan(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces" | "constraintProfile">,
  workspaceId?: string,
  referenceDate = new Date(),
): StudyPlan {
  const taskPool = workspaceId
    ? getIncompleteTasks(data).filter((task) => taskTouchesWorkspace(task, workspaceId))
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
    const workspace = task.workspace ?? FALLBACK_WORKSPACE;
    const remaining = Math.max(20, availableMinutes - consumed);
    const minutes = Math.min(task.estimatedMinutes ?? 30, remaining);
    consumed += minutes;

    return {
      id: `${task.id}-step`,
      title: task.title,
      reason:
        workspace.kind === "course"
          ? "It moves a graded or time-sensitive academic commitment."
          : workspace.id === "general"
            ? "It reduces life-admin drag and buys room for the rest of the week."
            : "It keeps an active project shipping without widening the day.",
      minutes,
      workspaceId: workspace.id === "general" ? undefined : workspace.id,
    };
  });

  return {
    title: workspaceId ? "Focused workspace plan" : "Constraint-aware weekly plan",
    summary: workspaceId
      ? `This flow respects the remaining ${data.constraintProfile.hoursRemainingThisWeek} hours while keeping the selected workspace moving.`
      : `This plan balances school, projects, and life admin against ${data.constraintProfile.hoursRemainingThisWeek} hours and $${data.constraintProfile.budgetRemainingThisWeek} still available this week.`,
    steps,
  };
}

export function getBuddyInsight(
  data: Pick<
    LifeOsSnapshot,
    "tasks" | "workspaces" | "events" | "materials" | "widgets" | "constraintProfile" | "gradebooks" | "milestones"
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
        title: "Orbit Assistant",
        summary: "This workspace does not have enough context yet.",
        bullets: ["Add one task or material to give the workspace shape."],
        actionLabel: "Open workspaces",
        actionHref: "/workspaces",
      };
    }

    return {
      title: bundle.workspace.kind === "course" ? "Study Assistant" : "Project Assistant",
      summary:
        bundle.workspace.kind === "course"
          ? `${bundle.workspace.shortLabel} needs a tighter sequence between assignments, class time, and grade pressure.`
          : `${bundle.workspace.shortLabel} will move best with one narrow shipping block instead of a long catch-up session.`,
      bullets: [
        bundle.tasks[0]
          ? `Open with ${bundle.tasks[0].title.toLowerCase()}.`
          : "Start by adding one concrete task to this workspace.",
        bundle.materials[0]
          ? `Use ${bundle.materials[0].title.toLowerCase()} as the source context.`
          : "Add one material summary so the assistant has planning context.",
        bundle.gradebook
          ? `Protect the grade floor while aiming for ${bundle.gradebook.targetGrade}%.`
          : bundle.milestones[0]
            ? `Keep ${bundle.milestones[0].title.toLowerCase()} moving this week.`
            : "Keep momentum with shorter, repeatable sessions.",
      ],
      actionLabel: "Open assistant",
      actionHref: "/assistant",
    };
  }

  return {
    title: "Orbit Assistant",
    summary:
      atRisk && recommendation
        ? `${atRisk.workspace.shortLabel} is the most exposed workspace, and ${recommendation.item.title.toLowerCase()} is the cleanest place to relieve pressure.`
        : "The board is steady enough to keep the next move simple.",
    bullets: [
      recommendation ? `Start with ${recommendation.item.title.toLowerCase()}.` : "Use one short task as your anchor.",
      atRisk ? `Watch ${atRisk.workspace.name.toLowerCase()} next.` : "No workspace is clearly slipping right now.",
      `You still have ${data.constraintProfile.hoursRemainingThisWeek} hours and $${data.constraintProfile.budgetRemainingThisWeek} to plan around this week.`,
    ],
    actionLabel: "Open assistant",
    actionHref: "/assistant",
  };
}

export function buildDailyNarrative(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces" | "constraintProfile" | "gradebooks" | "milestones">,
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
  data: Pick<LifeOsSnapshot, "workspaces" | "gradebooks" | "milestones" | "tasks">,
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
            Math.round(gradebook.targetGrade + (gradebook.targetGrade - gradebook.currentGrade) * 1.5),
          ),
        )
      : undefined;

    return [
      {
        workspace,
        title: `${gradebook.currentGrade}% current grade`,
        detail: nextPlanned
          ? `${nextPlanned.title} is the next grade-moving item.`
          : "No planned grade items are visible right now.",
        currentValue: gradebook.currentGrade,
        targetValue: gradebook.targetGrade,
        neededOnNext,
      } satisfies ProgressCard,
    ];
  });

  const projectCards = data.workspaces
    .filter((workspace) => workspace.kind === "project")
    .map((workspace) => {
      const milestones = data.milestones.filter((entry) => entry.workspaceId === workspace.id);
      const averageProgress = milestones.length
        ? Math.round(
            milestones.reduce((sum, milestone) => sum + milestone.progressPercent, 0) /
              milestones.length,
          )
        : 0;
      const openTasks = taskViews.filter(
        (task) => taskTouchesWorkspace(task, workspace.id) && !isTaskComplete(task),
      ).length;

      return {
        workspace,
        title: `${averageProgress}% milestone progress`,
        detail: `${openTasks} open linked tasks are still moving this project.`,
        currentValue: averageProgress,
        targetValue: 100,
      } satisfies ProgressCard;
    });

  return { courseCards, projectCards };
}

export function getGradeWhatIfCards(data: Pick<LifeOsSnapshot, "workspaces" | "gradebooks">) {
  return data.gradebooks.flatMap((gradebook) => {
    const workspace = data.workspaces.find((entry) => entry.id === gradebook.workspaceId);
    if (!workspace) {
      return [];
    }

    const nextItem = gradebook.items.find((item) => item.status === "planned");
    const neededScore = nextItem
      ? Math.min(
          100,
          Math.max(
            0,
            Math.round(gradebook.targetGrade + (gradebook.targetGrade - gradebook.currentGrade) * 1.25),
          ),
        )
      : undefined;
    const category = nextItem
      ? gradebook.categories.find((entry) => entry.id === nextItem.categoryId)
      : undefined;

    return [
      {
        workspace,
        currentGrade: gradebook.currentGrade,
        targetGrade: gradebook.targetGrade,
        nextItemTitle: nextItem?.title,
        neededScore,
        categoryLabel: category?.label,
      } satisfies GradeWhatIfCard,
    ];
  });
}

export function getSemesterGpaSnapshot(data: Pick<LifeOsSnapshot, "workspaces" | "gradebooks">) {
  const courseWorkspaces = data.workspaces.filter((workspace) => workspace.kind === "course");
  if (!courseWorkspaces.length) {
    return { gpa: 0, hours: 0 };
  }

  const points = courseWorkspaces.reduce((sum, workspace) => {
    const gradebook = data.gradebooks.find((entry) => entry.workspaceId === workspace.id);
    const grade = gradebook?.currentGrade ?? workspace.currentGrade ?? 0;
    const credits = workspace.creditHours ?? 3;
    const gpaPoints =
      grade >= 93 ? 4 : grade >= 90 ? 3.7 : grade >= 87 ? 3.3 : grade >= 83 ? 3 : grade >= 80 ? 2.7 : grade >= 77 ? 2.3 : 2;
    return sum + gpaPoints * credits;
  }, 0);
  const hours = courseWorkspaces.reduce((sum, workspace) => sum + (workspace.creditHours ?? 3), 0);

  return { gpa: Number((points / Math.max(hours, 1)).toFixed(2)), hours };
}

export function getHomeWidgetData(
  data: Pick<LifeOsSnapshot, "widgets" | "tasks" | "workspaces" | "events" | "constraintProfile" | "gradebooks" | "milestones">,
  referenceDate = new Date(),
) {
  const recommendation = getTodayRecommendations(data, referenceDate).primary;
  const urgent = getUrgentDeadlines(data, referenceDate, 3);
  const agenda = getAgendaGroups(data, referenceDate)[0];
  const atRiskCourses = getAtRiskWorkspaces(data, referenceDate, 3).filter(
    (entry) => entry.workspace.kind === "course",
  );
  const activeProjects = data.workspaces.filter(
    (workspace) => workspace.kind === "project" && workspace.active,
  );
  const narrative = buildDailyNarrative(data, referenceDate);

  return [...data.widgets]
    .sort((a, b) => a.order - b.order)
    .map((widget) => {
      switch (widget.kind) {
        case "primary_recommendation":
          return {
            widget,
            headline: recommendation?.item.title ?? "Protect some white space",
            detail: recommendation?.explanation ?? "Nothing urgent is pressing right now.",
            stats: recommendation ? recommendation.scoreBreakdown.slice(0, 3) : ["Calm board"],
            accentLabel: "Assistant pick",
          } satisfies HomeWidgetData;
        case "assistant_summary":
          return {
            widget,
            headline: "Orbit is shaping the day",
            detail: narrative,
            stats: [
              `${data.constraintProfile.hoursRemainingThisWeek} hours left`,
              `$${data.constraintProfile.budgetRemainingThisWeek} budget`,
            ],
            accentLabel: "Summary",
          } satisfies HomeWidgetData;
        case "timeline":
          return {
            widget,
            headline: agenda?.entries.length
              ? `${agenda.entries.length} items are visible today`
              : "Today still has breathing room",
            detail: agenda?.openWindows.join(" · ") ?? "The day is open enough to rebalance.",
            stats: agenda ? [`${agenda.loadPercent}% load`, agenda.pressureLabel] : ["Open day"],
            accentLabel: "Timeline",
          } satisfies HomeWidgetData;
        case "school_overview":
          return {
            widget,
            headline: atRiskCourses[0]
              ? `${atRiskCourses[0].workspace.shortLabel} needs attention`
              : "School is holding steady",
            detail: atRiskCourses[0]?.reason ?? "No course is clearly slipping right now.",
            stats: atRiskCourses.slice(0, 2).map((entry) => entry.workspace.shortLabel),
            accentLabel: "School",
          } satisfies HomeWidgetData;
        case "active_projects":
          return {
            widget,
            headline: `${activeProjects.length} active projects are still shipping`,
            detail:
              activeProjects[0]?.progressSummary ??
              "Projects are quiet enough to focus on school first.",
            stats: activeProjects.slice(0, 3).map((workspace) => workspace.shortLabel),
            accentLabel: "Projects",
          } satisfies HomeWidgetData;
        case "urgent_deadlines":
          return {
            widget,
            headline: urgent[0]?.title ?? "No urgent deadlines right now",
            detail:
              urgent[0]?.notes ??
              "The board does not have a near-term due-date crunch.",
            stats: urgent.slice(0, 3).map((task) => task.title),
            accentLabel: "Urgent",
          } satisfies HomeWidgetData;
        case "quick_actions":
          return {
            widget,
            headline: "Build dashboard, rebalance schedule, or focus a workspace",
            detail: "Orbit can update widgets, create study sessions, and explain why a task is winning.",
            stats: ["Build dashboard", "Generate weekly plan", "Explain priority"],
            accentLabel: "Actions",
          } satisfies HomeWidgetData;
      }
    });
}

export function buildWidgetReceipt(widgets: DashboardWidget[]): AssistantReceipt {
  return {
    title: "Dashboard updated",
    lines: widgets.map((widget) => `${widget.title} is now pinned to Home.`),
    href: "/home",
  };
}

function getAssistantCategory(result: CommandResult): AssistantResultCard["category"] {
  if (result.kind === "dashboard_update") {
    return "Dashboard Update";
  }
  if (result.kind === "plan_update" || result.kind === "schedule_update") {
    return "Plan";
  }
  if (
    result.kind === "priority_explanation" ||
    result.kind === "recommendation" ||
    result.kind === "workspace_focus"
  ) {
    return "Priority Explanation";
  }
  if (result.kind === "navigation") {
    return "Navigation";
  }
  return "Action";
}

function getAssistantAccent(category: AssistantResultCard["category"]): AssistantResultCard["accent"] {
  if (category === "Dashboard Update") {
    return "violet";
  }
  if (category === "Plan") {
    return "sky";
  }
  if (category === "Priority Explanation") {
    return "amber";
  }
  if (category === "Navigation") {
    return "emerald";
  }
  return "rose";
}

export function getAssistantResultCards(results: CommandResult[]): AssistantResultCard[] {
  return results.flatMap((result, index) => {
    if (result.kind === "message") {
      return [];
    }

    const category = getAssistantCategory(result);
    const accent = getAssistantAccent(category);
    const lines =
      "receipt" in result && result.receipt
        ? result.receipt.lines
        : result.kind === "plan_update"
          ? result.plan.steps.map((step) => `${step.title} · ${step.minutes} min`)
          : result.kind === "schedule_update"
            ? result.suggestions.map((entry) => `${entry.title} · ${entry.reason}`)
            : result.kind === "recommendation" && result.recommendation
              ? result.recommendation.scoreBreakdown
              : [];

    return [
      {
        id: `${result.intent}-${index}`,
        category,
        title:
          "receipt" in result && result.receipt
            ? result.receipt.title
            : result.message,
        summary: result.message,
        lines,
        href:
          "receipt" in result && result.receipt
            ? result.receipt.href
            : result.kind === "navigation"
              ? result.href
              : undefined,
        accent,
      } satisfies AssistantResultCard,
    ];
  });
}

export function getHomeBriefingItems(results: CommandResult[]): HomeBriefingItem[] {
  return results.flatMap((result, index) => {
    if (result.kind === "message") {
      return [];
    }

    return [
      {
        id: `${result.kind}-${index}`,
        label:
          result.kind === "dashboard_update"
            ? "Dashboard"
            : result.kind === "plan_update"
              ? "Plan"
              : result.kind === "schedule_update"
                ? "Schedule"
                : result.kind === "navigation"
                  ? "Route"
                  : result.kind === "priority_explanation" ||
                      result.kind === "recommendation" ||
                      result.kind === "workspace_focus"
                    ? "Why"
                    : "Action",
        summary:
          "receipt" in result && result.receipt
            ? `${result.receipt.title}: ${result.message}`
            : result.message,
        href:
          "receipt" in result && result.receipt
            ? result.receipt.href
            : result.kind === "navigation"
              ? result.href
              : undefined,
      } satisfies HomeBriefingItem,
    ];
  });
}

export function getRecentAssistantActivity(
  activity: AssistantActivityEvent[],
  limit = 8,
): AssistantActivityEvent[] {
  return activity.slice(0, limit);
}

export function getDashboardUpdateSummary(
  activity: AssistantActivityEvent[],
): { lastAt: string; addedCount: number; removedCount: number } | null {
  const entry = activity.find((event) => event.resultKind === "dashboard_update");
  if (!entry) {
    return null;
  }

  const addedLine = entry.receiptLines.find((line) => line.toLowerCase().startsWith("added:"));
  const removedLine = entry.receiptLines.find((line) => line.toLowerCase().startsWith("removed:"));
  const parseCount = (line?: string) =>
    line ? line.split(":")[1]?.split(",").filter(Boolean).length ?? 0 : 0;

  return {
    lastAt: entry.at,
    addedCount: parseCount(addedLine),
    removedCount: parseCount(removedLine),
  };
}

export function getWeeklyPlanSummary(plan: ActiveWeeklyPlan | null) {
  if (!plan) {
    return null;
  }

  const totalMinutes = plan.steps.reduce((sum, step) => sum + step.minutes, 0);
  const appliedCount = plan.steps.filter((step) => step.applied).length;
  const totalSteps = plan.steps.length;
  const scheduledDays = new Set(
    plan.steps.map((step) => step.scheduledFor.slice(0, 10)),
  );
  const nextStep = plan.steps.find((step) => !step.applied);

  return {
    totalMinutes,
    appliedCount,
    totalSteps,
    spanDays: scheduledDays.size,
    nextStep,
  };
}

export function getScheduleRebalanceSummary(suggestions: ScheduleSuggestion[]) {
  const pending = suggestions.filter((entry) => entry.status === "pending");
  const applied = suggestions.filter((entry) => entry.status === "applied");
  const netShiftedMinutes = applied.reduce(
    (sum, entry) => sum + (entry.estimatedMinutes ?? 0),
    0,
  );
  const affectedDays = Array.from(
    new Set(suggestions.flatMap((entry) => entry.affectedDays)),
  );

  return {
    pendingCount: pending.length,
    appliedCount: applied.length,
    netShiftedMinutes,
    affectedDays,
  };
}

export function getFocusedWorkspaceStatus(
  focusedWorkspaceId: string | null,
  workspaces: Workspace[],
  tasks: Task[],
): {
  workspace: Workspace | null;
  focusedTaskCount: number;
  homeRankingImpact: "promoted" | "neutral";
  surfaces: AssistantActivitySurface[];
} | null {
  if (!focusedWorkspaceId) {
    return null;
  }

  const workspace = workspaces.find((entry) => entry.id === focusedWorkspaceId) ?? null;
  if (!workspace) {
    return null;
  }

  const focusedTaskCount = tasks.filter(
    (task) =>
      task.primaryWorkspaceId === focusedWorkspaceId ||
      task.linkedWorkspaceIds.includes(focusedWorkspaceId),
  ).length;

  return {
    workspace,
    focusedTaskCount,
    homeRankingImpact: focusedTaskCount > 0 ? "promoted" : "neutral",
    surfaces: ["workspaces", "home", "assistant"],
  };
}

const SUGGESTION_ID_PREFIX = "suggestion";

function suggestionId(seed: string, index: number) {
  return `${SUGGESTION_ID_PREFIX}-${seed}-${index}`;
}

export function computeScheduleRebalance(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces" | "constraintProfile" | "events">,
  referenceDate: Date = new Date(),
): ScheduleSuggestion[] {
  const start = startOfWeek(referenceDate, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start, end: addDays(start, 6) });
  const agenda = getAgendaGroups(data, referenceDate);
  const taskViews = getIncompleteTasks(data);

  const dayMinutes = new Map<string, number>();
  days.forEach((day) => {
    const key = format(day, "yyyy-MM-dd");
    const match = agenda.find((entry) => entry.key === key);
    dayMinutes.set(key, match ? Math.round((match.loadPercent / 100) * 480) : 0);
  });

  const candidates: TaskView[] = taskViews
    .filter((task) => {
      const taskDate = getTaskDate(task);
      return Boolean(taskDate);
    })
    .sort((a, b) => {
      const priorityDiff = PRIORITY_WEIGHTS[b.priority] - PRIORITY_WEIGHTS[a.priority];
      if (priorityDiff !== 0) {
        return priorityDiff;
      }
      return compareTasksByUrgency(a, b);
    });

  const suggestions: ScheduleSuggestion[] = [];
  const generatedAt = referenceDate.toISOString();

  for (const task of candidates) {
    if (suggestions.length >= 5) {
      break;
    }

    const taskDate = getTaskDate(task);
    if (!taskDate) {
      continue;
    }

    const taskDayKey = format(taskDate, "yyyy-MM-dd");
    const currentLoad = dayMinutes.get(taskDayKey) ?? 0;
    const isHeavyDay = currentLoad >= 360;
    const estimatedMinutes = task.estimatedMinutes ?? 45;

    if (isHeavyDay) {
      const lighterDay = days.find((day) => {
        const key = format(day, "yyyy-MM-dd");
        if (key === taskDayKey) return false;
        if (isBefore(day, startOfDay(referenceDate))) return false;
        const load = dayMinutes.get(key) ?? 0;
        return load + estimatedMinutes <= 360;
      });

      if (lighterDay) {
        const toKey = format(lighterDay, "yyyy-MM-dd");
        const toAt = set(lighterDay, {
          hours: 15,
          minutes: 0,
          seconds: 0,
          milliseconds: 0,
        }).toISOString();

        suggestions.push({
          id: suggestionId(task.id, suggestions.length),
          generatedAt,
          kind: "shift",
          taskId: task.id,
          title: `Shift ${task.title} to ${format(lighterDay, "EEE")}`,
          reason: `${format(taskDate, "EEE")} is already heavy; ${format(lighterDay, "EEE")} has open room.`,
          fromAt: task.scheduledAt ?? task.dueAt,
          toAt,
          affectedDays: [taskDayKey, toKey],
          status: "pending",
          estimatedMinutes,
        });

        dayMinutes.set(toKey, (dayMinutes.get(toKey) ?? 0) + estimatedMinutes);
        dayMinutes.set(taskDayKey, Math.max(0, currentLoad - estimatedMinutes));
        continue;
      }
    }
  }

  // For unscheduled high-priority tasks, suggest insertion on earliest open day
  const unscheduledHighPriority = taskViews
    .filter((task) => !getTaskDate(task))
    .filter((task) => task.priority === "high" || task.priority === "critical")
    .slice(0, Math.max(0, 5 - suggestions.length));

  for (const task of unscheduledHighPriority) {
    const estimatedMinutes = task.estimatedMinutes ?? 45;
    const openDay = days.find((day) => {
      const key = format(day, "yyyy-MM-dd");
      if (isBefore(day, startOfDay(referenceDate))) return false;
      const load = dayMinutes.get(key) ?? 0;
      return load + estimatedMinutes <= 360;
    });

    if (openDay) {
      const toKey = format(openDay, "yyyy-MM-dd");
      const toAt = set(openDay, {
        hours: 14,
        minutes: 0,
        seconds: 0,
        milliseconds: 0,
      }).toISOString();

      suggestions.push({
        id: suggestionId(task.id, suggestions.length),
        generatedAt,
        kind: "insert",
        taskId: task.id,
        title: `Schedule ${task.title} on ${format(openDay, "EEE")}`,
        reason: `High-priority task has no slot yet; ${format(openDay, "EEE")} has an open window.`,
        toAt,
        affectedDays: [toKey],
        status: "pending",
        estimatedMinutes,
      });

      dayMinutes.set(toKey, (dayMinutes.get(toKey) ?? 0) + estimatedMinutes);
    }
  }

  return suggestions;
}

export function buildActiveWeeklyPlan(
  data: Pick<LifeOsSnapshot, "tasks" | "workspaces" | "constraintProfile" | "events">,
  referenceDate: Date = new Date(),
  focusedWorkspaceId?: string,
): ActiveWeeklyPlan {
  const base = getConstraintAwarePlan(data, focusedWorkspaceId, referenceDate);
  const start = startOfWeek(referenceDate, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start, end: addDays(start, 6) });
  const agenda = getAgendaGroups(data, referenceDate);

  const dayMinutes = new Map<string, number>();
  days.forEach((day) => {
    const key = format(day, "yyyy-MM-dd");
    const match = agenda.find((entry) => entry.key === key);
    dayMinutes.set(key, match ? Math.round((match.loadPercent / 100) * 480) : 0);
  });

  const steps: PlannedStep[] = base.steps.map((step, index) => {
    const openDay =
      days.find((day) => {
        const key = format(day, "yyyy-MM-dd");
        if (isBefore(day, startOfDay(referenceDate))) return false;
        const load = dayMinutes.get(key) ?? 0;
        return load + step.minutes <= 360;
      }) ?? days[Math.min(index + 1, days.length - 1)] ?? days[0];

    const key = format(openDay, "yyyy-MM-dd");
    const scheduledFor = set(openDay, {
      hours: 15,
      minutes: 0,
      seconds: 0,
      milliseconds: 0,
    }).toISOString();

    dayMinutes.set(key, (dayMinutes.get(key) ?? 0) + step.minutes);

    return {
      ...step,
      id: `${step.id}-${index}`,
      scheduledFor,
      applied: false,
    };
  });

  return {
    id: `plan-${referenceDate.getTime()}`,
    generatedAt: referenceDate.toISOString(),
    horizonDays: 7,
    title: base.title,
    summary: base.summary,
    steps,
  };
}

