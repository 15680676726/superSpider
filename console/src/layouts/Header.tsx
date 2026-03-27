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
import styles from "./index.module.less";

const { Header: AntHeader } = Layout;

const keyToDefaultLabel: Record<string, string> = {
  chat: "Chat",
  channels: "Channel Settings",
  "runtime-center": "Runtime Center",
  industry: "Industry",
  agents: "Agents",
  predictions: "Predictions",
  "capability-market": "Capability Market",
  system: "System Settings",
  "agent-config": "Agent Config",
  models: "Model Settings",
  environments: "Environment Settings",
  knowledge: "Knowledge",
  reports: "Reports",
  performance: "Performance",
  calendar: "Calendar",
};

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
  const label = keyToDefaultLabel[selectedKey] || "Runtime Center";

  return (
    <AntHeader className={`${styles.header} baize-header`}>
      <Space align="center" size={10}>
        {keyToIcon[selectedKey] ?? <Settings2 size={14} />}
        <span className={styles.headerTitle}>{label}</span>
      </Space>
      <Space size="middle" />
    </AntHeader>
  );
}
