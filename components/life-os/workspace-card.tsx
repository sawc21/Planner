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
    <Card className="surface-card border hairline">
      <CardHeader className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <span className={`inline-flex items-center gap-2 rounded-2xl px-3 py-2 ${workspace.colorToken}`}>
            <WorkspaceIcon icon={workspace.icon} className="size-4" />
            <span className="text-xs font-medium uppercase tracking-[0.2em]">
              {workspace.shortLabel}
            </span>
          </span>
          <span className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs text-muted-foreground">
            {WORKSPACE_KIND_LABELS[workspace.kind]}
          </span>
        </div>
        <div>
          <CardTitle className="font-heading text-2xl">{workspace.name}</CardTitle>
          <p className="mt-2 text-sm leading-6 text-foreground/72">
            {workspace.ownerLabel} · {workspace.progressSummary}
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl bg-[var(--surface-soft)] p-3">
            <BookMarked className="size-4 text-primary" />
            <p className="mt-2 text-sm font-medium text-foreground">{taskCount} open tasks</p>
          </div>
          <div className="rounded-2xl bg-[var(--surface-soft)] p-3">
            <Clock3 className="size-4 text-primary" />
            <p className="mt-2 text-sm font-medium text-foreground">{eventCount} scheduled events</p>
          </div>
          <div className="rounded-2xl bg-[var(--surface-soft)] p-3">
            <Files className="size-4 text-primary" />
            <p className="mt-2 text-sm font-medium text-foreground">{materialCount} materials</p>
          </div>
        </div>
        {risk ? (
          <div className="rounded-2xl bg-[var(--attention-soft)] p-4">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Risk signal
            </p>
            <p className="mt-2 text-sm text-foreground/82">{risk.reason}</p>
          </div>
        ) : null}
        <Link href={href} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-fit")}>
          Open workspace
          <ArrowRight className="size-4" />
        </Link>
      </CardContent>
    </Card>
  );
}
