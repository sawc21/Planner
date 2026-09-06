import Link from "next/link";
import { ArrowRight, BookMarked, Clock3, Files } from "lucide-react";

import { WorkspaceIcon } from "@/components/life-os/workspace-icon";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Workspace, WorkspaceRisk } from "@/lib/life-os/types";
import { WORKSPACE_KIND_LABELS } from "@/lib/life-os/types";
import { cn } from "@/lib/utils";

export function WorkspaceCard({
  workspace,
  href,
  taskCount,
  eventCount,
  materialCount,
  risk,
  focused = false,
}: {
  workspace: Workspace;
  href: string;
  taskCount: number;
  eventCount: number;
  materialCount: number;
  risk?: WorkspaceRisk;
  focused?: boolean;
}) {
  return (
    <Card
      data-focused={focused ? "true" : undefined}
      className={cn(
        "surface-card rounded-xl border hairline transition-transform duration-150 hover:-translate-y-0.5 hover:border-primary/24",
        focused && "ring-1 ring-emerald-300/40",
      )}
    >
      <Link href={href} className="block">
        <CardHeader className="space-y-3 pb-3">
          <div className="flex items-start justify-between gap-3">
            <span
              className={`inline-flex items-center gap-2 rounded-lg px-2 py-1 ${workspace.colorToken}`}
            >
              <WorkspaceIcon icon={workspace.icon} className="size-4" />
              <span className="font-mono text-[11px] font-medium uppercase tracking-[0.18em]">
                {workspace.shortLabel}
              </span>
              {focused ? (
                <span className="rounded-full bg-emerald-400/18 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-[0.16em] text-emerald-100">
                  Focused
                </span>
              ) : null}
            </span>
            <span className="rounded-md border hairline bg-[var(--surface-soft)] px-2 py-0.5 text-[11px] text-muted-foreground">
              {WORKSPACE_KIND_LABELS[workspace.kind]}
            </span>
          </div>
          <div>
            <CardTitle className="text-[18px] font-semibold tracking-tight">{workspace.name}</CardTitle>
            <p className="mt-1 text-[12px] leading-5 text-muted-foreground">
              {workspace.ownerLabel} · {workspace.progressSummary}
            </p>
            {workspace.currentGrade != null ? (
              <p className="mt-1.5 font-mono text-[11px] text-muted-foreground">
                Grade: <span className="text-foreground">{workspace.currentGrade.toFixed(1)}</span>
                {workspace.targetGrade != null ? <> / {workspace.targetGrade.toFixed(1)} target</> : null}
              </p>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-lg border hairline bg-[var(--surface-soft)] px-3 py-2.5">
              <BookMarked className="size-3.5 text-primary" />
              <p className="mt-1.5 text-[12px] font-medium text-foreground">
                <span className="font-mono">{taskCount}</span> open tasks
              </p>
            </div>
            <div className="rounded-lg border hairline bg-[var(--surface-soft)] px-3 py-2.5">
              <Clock3 className="size-3.5 text-primary" />
              <p className="mt-1.5 text-[12px] font-medium text-foreground">
                <span className="font-mono">{eventCount}</span> scheduled
              </p>
            </div>
            <div className="rounded-lg border hairline bg-[var(--surface-soft)] px-3 py-2.5">
              <Files className="size-3.5 text-primary" />
              <p className="mt-1.5 text-[12px] font-medium text-foreground">
                <span className="font-mono">{materialCount}</span> materials
              </p>
            </div>
          </div>
          {risk ? (
            <div className="rounded-lg border hairline bg-[var(--attention-soft)] px-3 py-2.5">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Risk signal
              </p>
              <p className="mt-1 text-[12px] text-foreground">{risk.reason}</p>
            </div>
          ) : null}
          <span className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-fit")}>
            Open workspace
            <ArrowRight className="size-4" />
          </span>
        </CardContent>
      </Link>
    </Card>
  );
}

