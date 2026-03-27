import { Card } from "@/ui";

interface PageHeaderProps {
  className?: string;
}

export function PageHeader({ className }: PageHeaderProps) {
  return (
    <Card className={`baize-page-header ${className || ""}`}>
      <div className="baize-page-header-content">
        <div>
          <h1 className="baize-page-header-title">{"环境变量"}</h1>
          <p className="baize-page-header-description">{"为智能体和技能配置键值环境变量。"}</p>
        </div>
      </div>
    </Card>
  );
}
