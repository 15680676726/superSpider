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
  chat: "聊天",
  channels: "渠道设置",
  "runtime-center": "运行中心",
  industry: "行业中枢",
  agents: "智能体",
  predictions: "预测",
  "capability-market": "能力市场",
  system: "系统设置",
  "agent-config": "智能体配置",
  models: "模型设置",
  environments: "环境设置",
  knowledge: "知识库",
  reports: "报告",
  performance: "绩效",
  calendar: "日历",
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
  const label = keyToDefaultLabel[selectedKey] || "运行中心";

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
