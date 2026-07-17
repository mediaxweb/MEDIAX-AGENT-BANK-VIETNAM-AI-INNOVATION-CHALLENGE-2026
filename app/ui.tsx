import type { ReactNode } from "react";

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}><span className="badge-dot" />{children}</span>;
}

export function Button({ children, variant = "primary", onClick, disabled = false, className = "" }: { children: ReactNode; variant?: string; onClick?: () => void; disabled?: boolean; className?: string }) {
  return <button className={`button ${variant} ${className}`} onClick={onClick} disabled={disabled}>{children}</button>;
}

export function PageHeading({ title, subtitle, children }: { title: string; subtitle: string; children?: ReactNode }) {
  return <div className="page-heading"><div><h1>{title}</h1><p>{subtitle}</p></div>{children && <div className="heading-actions">{children}</div>}</div>;
}
