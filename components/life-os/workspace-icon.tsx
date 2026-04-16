import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  BriefcaseBusiness,
  Compass,
  Cpu,
  GraduationCap,
  Heart,
  Languages,
  Sigma,
  Wallet,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  "book-open": BookOpen,
  briefcase: BriefcaseBusiness,
  compass: Compass,
  cpu: Cpu,
  "graduation-cap": GraduationCap,
  heart: Heart,
  languages: Languages,
  sigma: Sigma,
  wallet: Wallet,
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
