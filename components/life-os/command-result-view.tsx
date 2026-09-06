"use client";

import Link from "next/link";
import { ArrowRight, Check, Sparkles, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  ActiveWeeklyPlan,
  AssistantActivitySurface,
  CommandResult,
  ScheduleSuggestion,
} from "@/lib/life-os/types";
import { cn } from "@/lib/utils";

type Props = {
  result: CommandResult;
  onPlanApply?: () => void;
  onSuggestionApply?: (id: string) => void;
  onSuggestionDismiss?: (id: string) => void;
  onClearFocus?: () => void;
};

const SURFACE_LABELS: Record<AssistantActivitySurface, string> = {
  home: "Home",
  calendar: "Calendar",
  workspaces: "Workspaces",
  assignments: "Assignments",
  grades: "Grades",
  assistant: "Assistant",
};

function SurfaceChips({ surfaces }: { surfaces: AssistantActivitySurface[] }) {
  if (!surfaces.length) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {surfaces.map((surface) => (
        <Badge
          key={surface}
          variant="outline"
          className="rounded-full border-white/10 bg-background/50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground"
        >
          {SURFACE_LABELS[surface]}
        </Badge>
      ))}
    </div>
  );
}

function CardShell({
  accent,
  eyebrow,
  title,
  summary,
  children,
}: {
  accent: string;
  eyebrow: string;
  title: string;
  summary?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      data-kind={eyebrow.toLowerCase().replace(/\s+/g, "-")}
      className={cn(
        "rounded-2xl border hairline bg-background/70 p-4 shadow-sm",
        accent,
      )}
    >
      <span className="inline-flex rounded-full bg-background/60 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
        {eyebrow}
      </span>
      <p className="mt-2 text-[14px] font-semibold text-foreground">{title}</p>
      {summary ? (
        <p className="mt-1 text-[12px] leading-5 text-muted-foreground">{summary}</p>
      ) : null}
      {children}
    </div>
  );
}

function PlanUpdateCard({
  plan,
  appliedCount,
  onPlanApply,
}: {
  plan: ActiveWeeklyPlan;
  appliedCount: number;
  onPlanApply?: () => void;
}) {
  const totalSteps = plan.steps.length;
  const allApplied = appliedCount === totalSteps && totalSteps > 0;

  return (
    <CardShell
      accent="ring-1 ring-sky-300/15"
      eyebrow="Plan update"
      title={plan.title}
      summary={plan.summary}
    >
      <SurfaceChips surfaces={["home", "calendar", "assistant"]} />
      <div className="mt-3 space-y-2">
        {plan.steps.map((step) => (
          <div
            key={step.id}
            className="rounded-xl border hairline bg-background/55 px-3 py-2"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-[12px] font-medium text-foreground">{step.title}</p>
              <Badge
                variant="outline"
                className={cn(
                  "rounded-full border-white/10 px-2 py-0.5 text-[10px] font-medium",
                  step.applied
                    ? "bg-emerald-400/12 text-emerald-100"
                    : "bg-amber-400/10 text-amber-100",
                )}
              >
                {step.applied ? "Applied" : "Not yet"}
              </Badge>
            </div>
            <p className="mt-1 text-[11px] leading-4 text-muted-foreground">
              {step.minutes} min · {step.reason}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          onClick={onPlanApply}
          disabled={allApplied || !onPlanApply}
        >
          <Sparkles className="size-3.5" />
          {allApplied ? "All applied" : "Apply to this week"}
        </Button>
        <span className="text-[11px] text-muted-foreground">
          {appliedCount}/{totalSteps} applied
        </span>
      </div>
    </CardShell>
  );
}

function ScheduleUpdateCard({
  suggestions,
  onSuggestionApply,
  onSuggestionDismiss,
}: {
  suggestions: ScheduleSuggestion[];
  onSuggestionApply?: (id: string) => void;
  onSuggestionDismiss?: (id: string) => void;
}) {
  return (
    <CardShell
      accent="ring-1 ring-violet-300/15"
      eyebrow="Schedule update"
      title="Rebalance suggestions"
      summary={
        suggestions.length
          ? "Apply moves one at a time or dismiss ones you do not want."
          : "No schedule changes needed — the week already balances."
      }
    >
      <SurfaceChips surfaces={["calendar", "home"]} />
      {suggestions.length ? (
        <div className="mt-3 space-y-2">
          {suggestions.map((suggestion) => (
            <div
              key={suggestion.id}
              className="rounded-xl border hairline bg-background/55 px-3 py-2"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[12px] font-medium text-foreground">
                    {suggestion.title}
                  </p>
                  <p className="mt-1 text-[11px] leading-4 text-muted-foreground">
                    {suggestion.reason}
                  </p>
                </div>
                <Badge
                  variant="outline"
                  className={cn(
                    "rounded-full border-white/10 px-2 py-0.5 text-[10px] font-medium",
                    suggestion.status === "applied"
                      ? "bg-emerald-400/12 text-emerald-100"
                      : suggestion.status === "dismissed"
                        ? "bg-stone-400/12 text-stone-200"
                        : "bg-amber-400/10 text-amber-100",
                  )}
                >
                  {suggestion.status === "applied"
                    ? "Applied"
                    : suggestion.status === "dismissed"
                      ? "Dismissed"
                      : "Pending"}
                </Badge>
              </div>
              {suggestion.status === "pending" ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 rounded-full px-3 text-[11px]"
                    onClick={() => onSuggestionApply?.(suggestion.id)}
                  >
                    <Check className="size-3.5" />
                    Apply
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 rounded-full px-3 text-[11px]"
                    onClick={() => onSuggestionDismiss?.(suggestion.id)}
                  >
                    <X className="size-3.5" />
                    Dismiss
                  </Button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </CardShell>
  );
}

function WorkspaceFocusCard({
  workspaceId,
  affectedSurfaces,
  message,
  onClearFocus,
}: {
  workspaceId: string | null;
  affectedSurfaces: AssistantActivitySurface[];
  message: string;
  onClearFocus?: () => void;
}) {
  return (
    <CardShell
      accent="ring-1 ring-emerald-300/15"
      eyebrow="Workspace focus"
      title={message}
      summary={
        workspaceId
          ? "Orbit will rank tasks from this workspace first across Home, Assignments, and Calendar."
          : "Ranking is back to the default mix."
      }
    >
      <SurfaceChips surfaces={affectedSurfaces} />
      {workspaceId ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            href={`/workspaces/${workspaceId}`}
            className="inline-flex items-center gap-1 rounded-full border hairline bg-background/60 px-3 py-1 text-[11px] font-medium text-foreground"
          >
            Open workspace
            <ArrowRight className="size-3.5" />
          </Link>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 rounded-full px-3 text-[11px]"
            onClick={onClearFocus}
          >
            Clear focus
          </Button>
        </div>
      ) : null}
    </CardShell>
  );
}

function PriorityExplanationCard({ result }: { result: Extract<CommandResult, { kind: "priority_explanation" }> }) {
  const recommendation = result.recommendation;
  return (
    <CardShell
      accent="ring-1 ring-amber-300/15"
      eyebrow="Priority explanation"
      title={recommendation ? recommendation.item.title : "Board is calm"}
      summary={recommendation?.reason ?? result.message}
    >
      <SurfaceChips surfaces={result.affectedSurfaces} />
      {recommendation ? (
        <>
          <div className="mt-3 grid gap-1.5 text-[11px] text-muted-foreground">
            {recommendation.scoreBreakdown.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
          <div className="mt-3">
            <Link
              href="/assignments"
              className="inline-flex items-center gap-1 text-[11px] font-medium text-primary underline-offset-4 hover:underline"
            >
              Open in assignments
              <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </>
      ) : null}
    </CardShell>
  );
}

function DashboardUpdateCard({
  result,
}: {
  result: Extract<CommandResult, { kind: "dashboard_update" }>;
}) {
  return (
    <CardShell
      accent="ring-1 ring-violet-300/15"
      eyebrow="Dashboard update"
      title={result.message}
      summary={`${result.widgets.length} widgets pinned to Home.`}
    >
      <SurfaceChips surfaces={["home"]} />
      <div className="mt-3 grid gap-1 text-[11px] text-muted-foreground">
        {result.added.length ? (
          <p>
            <span className="text-emerald-200">+ </span>
            {result.added.join(", ")}
          </p>
        ) : null}
        {result.removed.length ? (
          <p>
            <span className="text-rose-200">− </span>
            {result.removed.join(", ")}
          </p>
        ) : null}
      </div>
      <div className="mt-3">
        <Link
          href="/home"
          className="inline-flex items-center gap-1 text-[11px] font-medium text-primary underline-offset-4 hover:underline"
        >
          Go home
          <ArrowRight className="size-3.5" />
        </Link>
      </div>
    </CardShell>
  );
}

function ActionReceiptCard({
  result,
}: {
  result: Extract<CommandResult, { kind: "action_receipt" }>;
}) {
  return (
    <CardShell
      accent="ring-1 ring-rose-300/15"
      eyebrow="Action receipt"
      title={result.receipt.title}
      summary={result.message}
    >
      {result.receipt.lines.length ? (
        <div className="mt-3 grid gap-1 text-[11px] text-muted-foreground">
          {result.receipt.lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      ) : null}
      {result.actions.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {result.actions.map((action) =>
            action.href ? (
              <Link
                key={action.label}
                href={action.href}
                className="inline-flex items-center gap-1 rounded-full border hairline bg-background/60 px-3 py-1 text-[11px] font-medium text-foreground"
              >
                {action.label}
                <ArrowRight className="size-3.5" />
              </Link>
            ) : (
              <span
                key={action.label}
                className="inline-flex items-center rounded-full border hairline bg-background/40 px-3 py-1 text-[11px] text-muted-foreground"
              >
                {action.label}
              </span>
            ),
          )}
        </div>
      ) : null}
    </CardShell>
  );
}

function MutationCard({
  result,
}: {
  result: Extract<CommandResult, { kind: "mutation" }>;
}) {
  return (
    <CardShell
      accent="ring-1 ring-rose-300/15"
      eyebrow="Action"
      title={result.receipt.title}
      summary={result.message}
    >
      <div className="mt-3 grid gap-1 text-[11px] text-muted-foreground">
        {result.receipt.lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
      {result.receipt.href ? (
        <div className="mt-3">
          <Link
            href={result.receipt.href}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-primary underline-offset-4 hover:underline"
          >
            Open linked surface
            <ArrowRight className="size-3.5" />
          </Link>
        </div>
      ) : null}
    </CardShell>
  );
}

function RecommendationCard({
  result,
}: {
  result: Extract<CommandResult, { kind: "recommendation" }>;
}) {
  const recommendation = result.recommendation;
  return (
    <CardShell
      accent="ring-1 ring-amber-300/15"
      eyebrow="Recommendation"
      title={recommendation ? recommendation.item.title : "Board is calm"}
      summary={result.message}
    >
      {recommendation ? (
        <div className="mt-3 grid gap-1 text-[11px] text-muted-foreground">
          {recommendation.scoreBreakdown.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      ) : null}
    </CardShell>
  );
}

function NavigationCard({
  result,
}: {
  result: Extract<CommandResult, { kind: "navigation" }>;
}) {
  return (
    <CardShell
      accent="ring-1 ring-emerald-300/15"
      eyebrow="Navigation"
      title={result.receipt?.title ?? "Navigation ready"}
      summary={result.message}
    >
      <div className="mt-3">
        <Link
          href={result.href}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-primary underline-offset-4 hover:underline"
        >
          Open
          <ArrowRight className="size-3.5" />
        </Link>
      </div>
    </CardShell>
  );
}

function MessageCard({
  result,
}: {
  result: Extract<CommandResult, { kind: "message" }>;
}) {
  return (
    <CardShell
      accent="ring-1 ring-stone-300/15"
      eyebrow="Message"
      title="Orbit says"
      summary={result.message}
    />
  );
}

export function CommandResultView({
  result,
  onPlanApply,
  onSuggestionApply,
  onSuggestionDismiss,
  onClearFocus,
}: Props) {
  switch (result.kind) {
    case "plan_update":
      return (
        <PlanUpdateCard
          plan={result.plan}
          appliedCount={result.appliedCount}
          onPlanApply={onPlanApply}
        />
      );
    case "schedule_update":
      return (
        <ScheduleUpdateCard
          suggestions={result.suggestions}
          onSuggestionApply={onSuggestionApply}
          onSuggestionDismiss={onSuggestionDismiss}
        />
      );
    case "workspace_focus":
      return (
        <WorkspaceFocusCard
          workspaceId={result.workspaceId}
          affectedSurfaces={result.affectedSurfaces}
          message={result.message}
          onClearFocus={onClearFocus}
        />
      );
    case "priority_explanation":
      return <PriorityExplanationCard result={result} />;
    case "dashboard_update":
      return <DashboardUpdateCard result={result} />;
    case "action_receipt":
      return <ActionReceiptCard result={result} />;
    case "mutation":
      return <MutationCard result={result} />;
    case "recommendation":
      return <RecommendationCard result={result} />;
    case "navigation":
      return <NavigationCard result={result} />;
    case "message":
      return <MessageCard result={result} />;
  }
}
