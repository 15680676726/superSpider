import { Layout, Space } from "antd";
import type { ReactNode } from "react";
import {
  BarChart3,
  Briefcase,
  Building2,
  BookOpen,
  CalendarDays,
  FileText,
  Gauge,
  MessageSquare,
  Radar,
  Settings2,
  ShieldCheck,
  Waypoints,
} from "lucide-react";
import { getRoutePresentation } from "./routePresentation";
import styles from "./index.module.less";

const { Header: AntHeader } = Layout;

const keyToIcon: Record<string, ReactNode> = {
  chat: <MessageSquare size={14} />,
  "runtime-center": <Radar size={14} />,
  agents: <Briefcase size={14} />,
  industry: <Building2 size={14} />,
  "capability-market": <Waypoints size={14} />,
  knowledge: <BookOpen size={14} />,
  reports: <FileText size={14} />,
  performance: <Gauge size={14} />,
  calendar: <CalendarDays size={14} />,
  predictions: <BarChart3 size={14} />,
  system: <ShieldCheck size={14} />,
};

interface HeaderProps {
  selectedKey: string;
}

export default function Header({ selectedKey }: HeaderProps) {
  const routePresentation = getRoutePresentation(selectedKey);

  return (
    <AntHeader className={`${styles.header} baize-header`}>
      <div className={styles.headerMeta}>
        <Space align="center" size={10}>
          {keyToIcon[selectedKey] ?? <Settings2 size={14} />}
          <span className={styles.headerTitle}>{routePresentation.title}</span>
        </Space>
        <span className={styles.headerDescription}>{routePresentation.description}</span>
      </div>
      <Space size="middle" />
    </AntHeader>
  );
}
