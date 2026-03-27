import type { ReactNode } from "react";
import { Card } from "antd";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

/**
 * Standardized page header card used across all pages.
 * Renders a glassmorphism card with title, optional description, and action buttons.
 */
export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <Card className={`baize-page-header ${className ?? ""}`}>
      <div className="baize-page-header-content">
        <div>
          <h1 className="baize-page-header-title">{title}</h1>
          {description && (
            <p className="baize-page-header-description">{description}</p>
          )}
        </div>
        {actions && (
          <div className="baize-page-header-actions">{actions}</div>
        )}
      </div>
    </Card>
  );
}
