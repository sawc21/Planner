"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { format } from "date-fns";
import {
  AlarmClockCheck,
  CalendarDays,
  CircleDollarSign,
  Command,
  LayoutDashboard,
  Menu,
  Sparkles,
} from "lucide-react";
import { useState } from "react";

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
  getOverdueItems,
  getTodayItems,
  getTodayRecommendations,
} from "@/lib/life-os/selectors";
import { useLifeOs } from "@/lib/life-os/state";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/tasks", label: "Tasks", icon: AlarmClockCheck },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/deadlines", label: "Deadlines", icon: CircleDollarSign },
  { href: "/command-center", label: "Command Center", icon: Command },
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
  const { items, focusTodayIds } = useLifeOs();
  const overdueCount = getOverdueItems(items).length;
  const todayCount = getTodayItems(items).length;
  const recommendation = getTodayRecommendations(items).primary;

  return (
    <div className="min-h-screen px-3 py-3 sm:px-4 sm:py-4">
      <div className="mx-auto flex max-w-[1560px] gap-4">
        <aside className="surface-panel sticky top-4 hidden h-[calc(100vh-2rem)] w-[292px] shrink-0 rounded-[28px] border hairline lg:flex lg:flex-col">
          <div className="space-y-5 p-5">
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground">
                Life OS
              </p>
              <div>
                <h2 className="font-heading text-3xl text-foreground">Plan gently.</h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  A calm cockpit for time-sensitive life admin, errands, and the week ahead.
                </p>
              </div>
            </div>
            <Separator />
          </div>

          <ScrollArea className="flex-1 px-4 pb-4">
            <SidebarLinks pathname={pathname} />
          </ScrollArea>

          <div className="border-t hairline p-4">
            <div className="rounded-[24px] bg-white/70 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Daily anchor
              </p>
              <p className="mt-2 font-medium text-foreground">
                {recommendation?.item.title ?? "Let today stay spacious."}
              </p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {recommendation?.reason ??
                  "You have enough margin to choose one meaningful thing."}
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
                  <p className="mt-1 text-sm text-foreground">
                    {recommendation
                      ? `Lead with ${recommendation.item.title.toLowerCase()}.`
                      : "Your board looks calm today."}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="rounded-full bg-white/70 px-3 py-2 text-muted-foreground">
                  {todayCount} active today
                </span>
                <span className="rounded-full bg-white/70 px-3 py-2 text-muted-foreground">
                  {overdueCount} overdue
                </span>
                <span className="rounded-full bg-white/70 px-3 py-2 text-muted-foreground">
                  {focusTodayIds.length} focus picks
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
              Move through the week with less noise and a stronger sense of sequence.
            </SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-5">
            <SidebarLinks pathname={pathname} onNavigate={() => setMobileNavOpen(false)} />
            <Separator className="my-5" />
            <div className="rounded-[24px] bg-white/80 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Next best move
              </p>
              <p className="mt-2 font-medium text-foreground">
                {recommendation?.item.title ?? "Protect some white space."}
              </p>
              <Link
                href="/command-center"
                onClick={() => setMobileNavOpen(false)}
                className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-4")}
              >
                <Sparkles className="size-4" />
                Open Command Center
              </Link>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
