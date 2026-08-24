import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  PauseCircle,
  Radio,
} from "lucide-react";
import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-heading">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-header">
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const Icon =
    normalized === "running" || normalized === "available"
      ? Radio
      : normalized === "completed" || normalized === "ready" || normalized === "ok"
        ? CheckCircle2
        : normalized === "failed" || normalized === "high"
          ? AlertCircle
          : normalized === "created"
            ? Clock3
            : PauseCircle;

  return (
    <span className={`status-badge status-${normalized.replaceAll("_", "-")}`}>
      <Icon size={13} aria-hidden="true" />
      <span>{status.replaceAll("_", " ")}</span>
    </span>
  );
}

export function InlineAlert({ children }: { children: ReactNode }) {
  return (
    <div className="inline-alert" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export function LoadingState({ label = "Loading data" }: { label?: string }) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="spinner" size={19} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-state-mark" aria-hidden="true" />
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
