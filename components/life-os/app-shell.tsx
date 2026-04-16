"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { differenceInCalendarDays, endOfWeek, format, startOfWeek } from "date-fns";
import {
  BookOpenCheck,
  BriefcaseBusiness,
  CalendarDays,
  Command,
  GraduationCap,
  LayoutDashboard,
  Menu,
  Plus,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useState } from "react";

import { CommandPanel } from "@/components/life-os/command-panel";
import { Button, buttonVariants } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  getAtRiskWorkspaces,
  getOverdueTasks,
  getTodayRecommendations,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Today", icon: LayoutDashboard },
  { href: "/agenda", label: "Agenda", icon: CalendarDays },
  { href: "/workspaces", label: "Workspaces", icon: GraduationCap },
  { href: "/tasks", label: "Tasks", icon: BookOpenCheck },
  { href: "/progress", label: "Progress", icon: TrendingUp },
  { href: "/command", label: "Command", icon: Command },
];

function SidebarLinks({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <nav className="space-y-1.5">
      {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
        const active = pathname === href || (href !== "/" && pathname.startsWith(href));

        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-3 rounded-2xl px-3 py-3 text-sm font-medium transition-colors",
              active
                ? "bg-[var(--sidebar-accent)] text-foreground shadow-sm"
                : "text-muted-foreground hover:bg-white/70 hover:text-foreground",
            )}
          >
            <span
              className={cn(
                "rounded-xl p-2",
                active ? "bg-white/80 text-primary" : "bg-transparent text-muted-foreground",
              )}
            >
              <Icon className="size-4" />
            </span>
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const {
    workspaces,
    tasks,
    gradebooks,
    progressRecords,
    constraintProfile,
    openCommandPanel,
  } = useLifeOs();
  const recommendation = getTodayRecommendations({
    tasks,
    workspaces,
    constraintProfile,
  }).primary;
  const overdueTasks = getOverdueTasks({ tasks, workspaces }).length;
  const atRiskWorkspaces = getAtRiskWorkspaces({
    workspaces,
    tasks,
    gradebooks,
    progressRecords,
  });
  const today = new Date();
  const weekStart = startOfWeek(today, { weekStartsOn: 1 });
  const weekEnd = endOfWeek(today, { weekStartsOn: 1 });
  const weekProgress = Math.round(
    ((differenceInCalendarDays(today, weekStart) + 1) /
      (differenceInCalendarDays(weekEnd, weekStart) + 1)) *
      100,
  );

  return (
    <div className="min-h-screen px-3 py-3 sm:px-4 sm:py-4">
      <div className="mx-auto flex max-w-[1560px] gap-4">
        <aside className="surface-panel sticky top-4 hidden h-[calc(100vh-2rem)] w-[300px] shrink-0 rounded-[28px] border hairline lg:flex lg:flex-col">
          <div className="space-y-5 p-5">
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground">
                Life OS
              </p>
              <div>
                <h2 className="font-heading text-3xl text-foreground/95">Plan, track, study.</h2>
                <p className="mt-2 text-sm leading-6 text-foreground/72">
                  One shared system for life admin, coursework, and structured learning flows.
                </p>
              </div>
            </div>

            <div className="rounded-[24px] bg-white/74 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Utility zone
                  </p>
                  <p className="mt-1 font-medium text-foreground">
                    {format(today, "EEEE, MMM d")}
                  </p>
                  <p className="mt-1 text-sm text-foreground/72">
                    {overdueTasks} overdue tasks still need relief, with {constraintProfile.hoursRemainingThisWeek} study hours and ${constraintProfile.budgetRemainingThisWeek} left this week.
                  </p>
                </div>
                <Button size="icon-sm" onClick={openCommandPanel} aria-label="Quick add command">
                  <Plus className="size-4" />
                </Button>
              </div>
              <div className="mt-4 h-2 rounded-full bg-[var(--surface-soft)]">
                <div
                  className="h-2 rounded-full bg-primary transition-[width] duration-300"
                  style={{ width: `${weekProgress}%` }}
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-foreground/72">
                <span className="rounded-full bg-[var(--surface-soft)] px-3 py-1">
                  {weekProgress}% through the week
                </span>
                <span className="rounded-full bg-[var(--surface-soft)] px-3 py-1">
                  {overdueTasks} overdue
                </span>
              </div>
            </div>
          </div>

          <ScrollArea className="flex-1 px-4 pb-4">
            <SidebarLinks pathname={pathname} />
          </ScrollArea>

          <div className="border-t hairline p-4">
            <div className="rounded-[24px] bg-white/70 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Daily anchor
              </p>
              <p className="mt-2 font-medium text-foreground/95">
                {recommendation?.item.title ?? "Protect some white space."}
              </p>
              <p className="mt-1 text-sm leading-6 text-foreground/72">
                {recommendation?.explanation ??
                  "The board is calm enough to choose one meaningful next move."}
              </p>
            </div>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <div className="surface-panel mb-4 rounded-[28px] border hairline px-4 py-4 sm:px-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  size="icon-sm"
                  className="lg:hidden"
                  onClick={() => setMobileNavOpen(true)}
                  aria-label="Open navigation"
                >
                  <Menu className="size-4" />
                </Button>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">
                    {format(new Date(), "EEEE, MMMM d")}
                  </p>
                  <p className="mt-1 text-sm font-medium text-foreground/88">
                    {recommendation
                      ? `Lead with ${recommendation.item.title.toLowerCase()}.`
                      : "Your board looks calm today."}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="rounded-full bg-white/70 px-3 py-2 text-muted-foreground">
                  {atRiskWorkspaces.length} at-risk workspaces
                </span>
                <span className="rounded-full bg-white/70 px-3 py-2 text-muted-foreground">
                  {overdueTasks} overdue tasks
                </span>
                <span className="rounded-full bg-white/70 px-3 py-2 text-muted-foreground">
                  {constraintProfile.hoursRemainingThisWeek} hours left
                </span>
                <span className="rounded-full bg-white/70 px-3 py-2 text-muted-foreground">
                  ${constraintProfile.budgetRemainingThisWeek} budget left
                </span>
              </div>
            </div>
          </div>

          <main className="pb-6">{children}</main>
        </div>
      </div>

      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent side="left" className="w-[88vw] max-w-sm bg-[var(--surface-soft)]">
          <SheetHeader className="space-y-2">
            <SheetTitle className="font-heading text-3xl">Life OS</SheetTitle>
            <SheetDescription>
              A shared operating system for study flows, life admin, and the week ahead.
            </SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-5">
            <SidebarLinks pathname={pathname} onNavigate={() => setMobileNavOpen(false)} />
            <Separator className="my-5" />
            <div className="rounded-[24px] bg-white/80 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Next best move
              </p>
              <p className="mt-2 font-medium text-foreground/95">
                {recommendation?.item.title ?? "Protect some white space."}
              </p>
              <Link
                href="/command"
                onClick={() => setMobileNavOpen(false)}
                className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-4")}
              >
                <Sparkles className="size-4" />
                Open Command
              </Link>
              <Button
                variant="outline"
                size="sm"
                className="mt-2 w-full"
                onClick={() => {
                  setMobileNavOpen(false);
                  openCommandPanel();
                }}
              >
                <Plus className="size-4" />
                Quick add
              </Button>
              <div className="mt-4 rounded-2xl bg-[var(--surface-soft)] p-3">
                <BriefcaseBusiness className="size-4 text-primary" />
                <p className="mt-2 text-sm text-foreground/82">
                  {atRiskWorkspaces[0]
                    ? `${atRiskWorkspaces[0].workspace.shortLabel} is currently the most exposed workspace.`
                    : "No workspace is clearly slipping right now."}
                </p>
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>
      <CommandPanel />
    </div>
  );
}
