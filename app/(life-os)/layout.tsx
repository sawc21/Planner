import type { ReactNode } from "react";

import { AppShell } from "@/components/life-os/app-shell";

export default function LifeOsLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
