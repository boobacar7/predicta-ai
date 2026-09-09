import {
  Activity,
  CalendarDays,
  LayoutGrid,
  MessageSquare,
  Shield,
  Sparkles,
  User,
  Users,
  Diamond,
  BarChart3,
  type LucideIcon,
} from "lucide-react";
import type { NavItem } from "@/lib/navigation";

const icons: Record<NavItem["icon"], LucideIcon> = {
  layout: LayoutGrid,
  calendar: CalendarDays,
  spark: Sparkles,
  diamond: Diamond,
  chart: BarChart3,
  activity: Activity,
  message: MessageSquare,
  shield: Shield,
  users: Users,
  user: User,
  profile: User,
};

export function NavIcon({ name, className }: { name: NavItem["icon"]; className?: string }) {
  const Icon = icons[name];
  return <Icon className={className} aria-hidden="true" />;
}
