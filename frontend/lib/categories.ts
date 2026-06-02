import {
  Banknote,
  Bus,
  HeartPulse,
  Home,
  PiggyBank,
  Repeat,
  ShoppingBag,
  Tag,
  Utensils,
  type LucideIcon,
} from "lucide-react";

// top-level category -> icon, falls back to a generic tag
const ICONS: Record<string, LucideIcon> = {
  food: Utensils,
  shopping: ShoppingBag,
  housing: Home,
  transport: Bus,
  subscriptions: Repeat,
  health: HeartPulse,
  savings: PiggyBank,
  income: Banknote,
};

export function categoryIcon(category: string): LucideIcon {
  return ICONS[category.split(".")[0]] ?? Tag;
}
