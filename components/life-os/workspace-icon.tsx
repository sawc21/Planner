import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  Bot,
  FolderOpen,
  Radar,
  Rocket,
  Sparkles,
  Cpu,
  GraduationCap,
  Sigma,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  "book-open": BookOpen,
  bot: Bot,
  cpu: Cpu,
  "folder-open": FolderOpen,
  "graduation-cap": GraduationCap,
  radar: Radar,
  rocket: Rocket,
  sigma: Sigma,
  sparkles: Sparkles,
};

export function WorkspaceIcon({
  icon,
  className,
}: {
  icon: string;
  className?: string;
}) {
  const Icon = ICONS[icon] ?? BookOpen;
  return <Icon className={className} />;
}
