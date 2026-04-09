import type { ReactNode } from "react";
import { Card } from "antd";

interface PageHeaderStat {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
}

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  stats?: PageHeaderStat[];
  actions?: ReactNode;
  aside?: ReactNode;
  className?: string;
}

/**
 * Standardized page header card used across all pages.
 * Renders a glassmorphism card with title, optional description, and action buttons.
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  stats,
  actions,
  aside,
  className,
}: PageHeaderProps) {
  return (
    <Card className={`baize-page-header ${className ?? ""}`}>
      <div className="baize-page-header-content">
        <div>
          {eyebrow ? <div className="baize-page-header-eyebrow">{eyebrow}</div> : null}
          <h1 className="baize-page-header-title">{title}</h1>
          {description && (
            <p className="baize-page-header-description">{description}</p>
          )}
          {stats?.length ? (
            <div className="baize-page-header-stats" aria-label={`${title} stats`}>
              {stats.map((stat) => (
                <div key={stat.label} className="baize-page-header-stat">
                  <span className="baize-page-header-stat-label">{stat.label}</span>
                  <strong className="baize-page-header-stat-value">{stat.value}</strong>
                  {stat.hint ? (
                    <span className="baize-page-header-stat-hint">{stat.hint}</span>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
        {(actions || aside) && (
          <div className="baize-page-header-side">
            {aside ? <div className="baize-page-header-aside">{aside}</div> : null}
            {actions ? (
              <div className="baize-page-header-actions">{actions}</div>
            ) : null}
          </div>
        )}
      </div>
    </Card>
  );
}
