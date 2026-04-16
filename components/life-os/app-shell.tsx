"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { differenceInCalendarDays, endOfWeek, format, startOfWeek } from "date-fns";
import {
  ArrowUpRight,
  BadgeCheck,
  BookOpenCheck,
  CalendarDays,
  Command,
  FolderKanban,
  GraduationCap,
  House,
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
  { href: "/home", label: "Home", icon: House },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/workspaces", label: "Workspaces", icon: GraduationCap },
  { href: "/assignments", label: "Assignments", icon: BookOpenCheck },
  { href: "/grades", label: "Grades", icon: TrendingUp },
  { href: "/assistant", label: "Assistant", icon: Command },
];

function SidebarLinks({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <nav className="space-y-1">
      {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
        const active = pathname === href || (href !== "/" && pathname.startsWith(href));

        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-2 rounded-lg px-2.5 py-2 text-[12px] font-medium transition-colors",
              active
                ? "bg-[var(--sidebar-accent)] text-foreground"
                : "text-muted-foreground hover:bg-[var(--sidebar-accent)]/60 hover:text-foreground",
            )}
          >
            <span
              className={cn(
                "rounded-md p-1.5 transition-colors",
                active ? "bg-primary/14 text-primary" : "bg-transparent text-muted-foreground",
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
    milestones,
    gradebooks,
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
    milestones,
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
      <div className="mx-auto flex max-w-[1500px] gap-3">
        <aside className="surface-glass sticky top-3 hidden h-[calc(100vh-1.5rem)] w-[248px] shrink-0 rounded-2xl lg:flex lg:flex-col">
          <div className="space-y-4 p-4">
            <div className="space-y-1">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-primary/86">
                Orbit OS
              </p>
              <div>
                <h2 className="text-[18px] font-semibold tracking-tight text-foreground">
                  Plan, study, ship.
                </h2>
                <p className="mt-1 text-[12px] leading-5 text-muted-foreground">
                  A visual operating system for school and side-work.
                </p>
              </div>
            </div>

            <div className="rounded-xl border hairline bg-background/58 p-3.5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    System status
                  </p>
                  <p className="mt-1 text-[12px] font-medium text-foreground">
                    {format(today, "EEE, MMM d")}
                  </p>
                  <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                    {overdueTasks} urgent · {constraintProfile.hoursRemainingThisWeek}h left · ${constraintProfile.budgetRemainingThisWeek} budget
                  </p>
                </div>
                <Button size="icon-sm" onClick={openCommandPanel} aria-label="Quick add command">
                  <Plus className="size-4" />
                </Button>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/8">
                <div className="h-1.5 rounded-full bg-primary transition-[width] duration-300" style={{ width: `${weekProgress}%` }} />
              </div>
            </div>
          </div>

          <ScrollArea className="flex-1 px-3 pb-3">
            <SidebarLinks pathname={pathname} />
          </ScrollArea>

          <div className="border-t hairline p-3">
            <div className="rounded-xl border hairline bg-background/58 p-3.5">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Assistant anchor
              </p>
              <p className="mt-2 text-[12px] font-medium text-foreground">
                {recommendation?.item.title ?? "Protect open space."}
              </p>
              <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                {recommendation?.explanation ?? "The board is calm enough to keep one narrow focus."}
              </p>
              <Link href="/assistant" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-3 w-full justify-start")}>
                <Sparkles className="size-4" />
                Open workbench
              </Link>
            </div>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <div className="surface-panel mb-3 rounded-2xl border hairline px-3.5 py-2.5 sm:px-4">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-2.5">
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
                  <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    System rail
                  </p>
                  <p className="mt-1 text-[12px] font-medium text-foreground">
                    {recommendation
                      ? `Orbit is leading with ${recommendation.item.title.toLowerCase()}.`
                      : "Orbit sees a calm board."}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                <span className="rounded-full border hairline bg-background/55 px-2.5 py-1 text-muted-foreground">
                  <span className="font-mono text-foreground">{atRiskWorkspaces.length}</span> at-risk
                </span>
                <span className="rounded-full border hairline bg-background/55 px-2.5 py-1 text-muted-foreground">
                  <span className="font-mono text-foreground">{overdueTasks}</span> urgent
                </span>
                <span className="rounded-full border hairline bg-background/55 px-2.5 py-1 text-muted-foreground">
                  <span className="font-mono text-foreground">{constraintProfile.hoursRemainingThisWeek}h</span> left
                </span>
                <Link href="/assistant" className="inline-flex items-center gap-1 rounded-full border hairline bg-background/55 px-2.5 py-1 text-muted-foreground transition-colors hover:text-foreground">
                  Assistant
                  <ArrowUpRight className="size-3.5" />
                </Link>
              </div>
            </div>
          </div>

          <main className="pb-4">{children}</main>
        </div>
      </div>

      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent side="left" className="surface-glass w-[88vw] max-w-sm">
          <SheetHeader className="space-y-1">
            <SheetTitle className="text-xl font-semibold tracking-tight">Orbit OS</SheetTitle>
            <SheetDescription>
              A visual operating system for school and side-work.
            </SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-5">
            <SidebarLinks pathname={pathname} onNavigate={() => setMobileNavOpen(false)} />
            <Separator className="my-4" />
            <div className="rounded-xl border hairline bg-background/58 p-3.5">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Next move
              </p>
              <p className="mt-2 text-[12px] font-medium text-foreground">
                {recommendation?.item.title ?? "Protect open space."}
              </p>
              <Link
                href="/assistant"
                onClick={() => setMobileNavOpen(false)}
                className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-3 w-full justify-start")}
              >
                <Sparkles className="size-4" />
                Open Assistant
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
                Quick run
              </Button>
              <div className="mt-3 rounded-lg bg-[var(--surface-soft)]/88 p-3">
                <FolderKanban className="size-4 text-primary" />
                <p className="mt-2 text-[12px] leading-5 text-muted-foreground">
                  {atRiskWorkspaces[0]
                    ? `${atRiskWorkspaces[0].workspace.shortLabel} is the most exposed workspace.`
                    : "No workspace is clearly slipping right now."}
                </p>
                <div className="mt-2 inline-flex items-center gap-1.5 rounded-full border hairline bg-background/55 px-2 py-0.5 text-[10px] text-muted-foreground">
                  <BadgeCheck className="size-3.5 text-primary" />
                  Every surface deep-links into Orbit actions.
                </div>
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>
      <CommandPanel />
    </div>
  );
}
