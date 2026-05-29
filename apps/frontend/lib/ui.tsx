import {
  displayStatusClassName,
  displayStatusLabel,
  statusClassName,
  statusLabel,
} from "./format";

type StatusBadgeProps = {
  status: string;
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${statusClassName(
        status,
      )}`}
    >
      {statusLabel(status)}
    </span>
  );
}

type DisplayStatusBadgeProps = {
  source: {
    isDisplay?: boolean | null;
    is_display?: boolean | null;
    hidden?: boolean | null;
  };
};

export function DisplayStatusBadge({ source }: DisplayStatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${displayStatusClassName(
        source,
      )}`}
    >
      {displayStatusLabel(source)}
    </span>
  );
}

type ErrorPanelProps = {
  message: string;
  onRetry?: () => void;
};

export function ErrorPanel({ message, onRetry }: ErrorPanelProps) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 shadow-sm">
      <div className="font-semibold">เกิดข้อผิดพลาด</div>
      <p className="mt-1">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-rose-300 bg-white px-3 py-2 font-medium text-rose-800 shadow-sm hover:bg-rose-100"
        >
          ลองใหม่
        </button>
      ) : null}
    </div>
  );
}

type SuccessPanelProps = {
  title?: string;
  children: React.ReactNode;
};

export function SuccessPanel({ title = "ทำรายการสำเร็จ", children }: SuccessPanelProps) {
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900 shadow-sm">
      <div className="font-semibold">{title}</div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

export function LoadingPanel() {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 text-sm text-zinc-600 shadow-sm">
      <div className="h-2 w-24 animate-pulse rounded-full bg-zinc-200" />
      <div className="mt-4 h-2 w-44 animate-pulse rounded-full bg-zinc-100" />
    </div>
  );
}

export function EmptyPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-600 shadow-sm">
      {children}
    </div>
  );
}

type PageHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
};

export function PageHeader({ eyebrow, title, description, action }: PageHeaderProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-l-4 border-zinc-950 px-5 py-5 sm:flex sm:items-start sm:justify-between sm:gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            {eyebrow}
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-zinc-950">{title}</h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-600">{description}</p>
        </div>
        {action ? <div className="mt-4 shrink-0 sm:mt-0">{action}</div> : null}
      </div>
    </div>
  );
}

type StatCardProps = {
  label: string;
  value: string | number;
  tone?: "zinc" | "emerald" | "amber" | "rose" | "sky";
};

export function StatCard({ label, value, tone = "zinc" }: StatCardProps) {
  const toneClassName = {
    zinc: "border-zinc-200 bg-white text-zinc-950",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-950",
    amber: "border-amber-200 bg-amber-50 text-amber-950",
    rose: "border-rose-200 bg-rose-50 text-rose-950",
    sky: "border-sky-200 bg-sky-50 text-sky-950",
  }[tone];

  return (
    <div className={`rounded-lg border p-4 shadow-sm ${toneClassName}`}>
      <div className="text-xs font-semibold uppercase tracking-wide opacity-70">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

export function TableShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

export const actionLinkClassName =
  "inline-flex items-center justify-center rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 shadow-sm hover:border-zinc-300 hover:bg-zinc-50";

export const approveButtonClassName =
  "inline-flex items-center justify-center rounded-md border border-emerald-300 bg-emerald-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60";

export const rejectButtonClassName =
  "inline-flex items-center justify-center rounded-md border border-rose-200 bg-white px-3 py-2 text-sm font-semibold text-rose-700 shadow-sm hover:border-rose-300 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60";

export const syncButtonClassName =
  "inline-flex items-center justify-center rounded-md border border-sky-300 bg-sky-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-60";

export const productionSyncButtonClassName =
  "inline-flex items-center justify-center rounded-md border border-zinc-950 bg-zinc-950 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60";
