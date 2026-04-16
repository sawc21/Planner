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
}: {
  workspace: Workspace;
  href: string;
  taskCount: number;
  eventCount: number;
  materialCount: number;
  risk?: WorkspaceRisk;
}) {
  return (
    <Card className="surface-card rounded-xl border hairline">
      <CardHeader className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <span
            className={`inline-flex items-center gap-2 rounded-lg px-2.5 py-1.5 ${workspace.colorToken}`}
          >
            <WorkspaceIcon icon={workspace.icon} className="size-4" />
            <span className="font-mono text-[11px] font-medium uppercase tracking-[0.18em]">
              {workspace.shortLabel}
            </span>
          </span>
          <span className="rounded-md border hairline bg-[var(--surface-soft)] px-2 py-0.5 text-[11px] text-muted-foreground">
            {WORKSPACE_KIND_LABELS[workspace.kind]}
          </span>
        </div>
        <div>
          <CardTitle className="text-xl font-semibold tracking-tight">
            {workspace.name}
          </CardTitle>
          <p className="mt-1.5 text-[13px] leading-5 text-muted-foreground">
            {workspace.ownerLabel} · {workspace.progressSummary}
          </p>
          {workspace.currentGrade != null ? (
            <p className="mt-2 font-mono text-[12px] text-muted-foreground">
              Grade:{" "}
              <span className="text-foreground">
                {workspace.currentGrade.toFixed(1)}
              </span>
              {workspace.targetGrade != null ? (
                <> / {workspace.targetGrade.toFixed(1)} target</>
              ) : null}
            </p>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-3">
          <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3">
            <BookMarked className="size-4 text-primary" />
            <p className="mt-2 text-[13px] font-medium text-foreground">
              <span className="font-mono">{taskCount}</span> open tasks
            </p>
          </div>
          <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3">
            <Clock3 className="size-4 text-primary" />
            <p className="mt-2 text-[13px] font-medium text-foreground">
              <span className="font-mono">{eventCount}</span> scheduled
            </p>
          </div>
          <div className="rounded-lg border hairline bg-[var(--surface-soft)] p-3">
            <Files className="size-4 text-primary" />
            <p className="mt-2 text-[13px] font-medium text-foreground">
              <span className="font-mono">{materialCount}</span> materials
            </p>
          </div>
        </div>
        {risk ? (
          <div className="rounded-lg border hairline bg-[var(--attention-soft)] p-3.5">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Risk signal
            </p>
            <p className="mt-1.5 text-[13px] text-foreground">{risk.reason}</p>
          </div>
        ) : null}
        <Link
          href={href}
          className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-fit")}
        >
          Open workspace
          <ArrowRight className="size-4" />
        </Link>
      </CardContent>
    </Card>
  );
}
