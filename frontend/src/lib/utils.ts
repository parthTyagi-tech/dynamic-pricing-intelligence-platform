import type { Kpi } from "../types/domain";

export const cn = (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(" ");
export const money = (value: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
export const moneyPrecise = (value: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
export const percent = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
export const kpiTone = (kpi: Kpi) => ({
  indigo: "accent-indigo",
  emerald: "accent-emerald",
  rose: "accent-rose",
  violet: "accent-violet",
}[kpi.accent]);
