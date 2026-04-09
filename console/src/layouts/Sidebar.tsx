import {
  Badge,
  Button,
  Layout,
  Menu,
  Modal,
  Spin,
  type MenuProps,
} from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  Box,
  Building2,
  CalendarDays,
  Cpu,
  FileText,
  Gauge,
  Globe,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Radar,
  Settings,
  ShieldCheck,
  Waypoints,
  Wifi,
} from "lucide-react";
import { LazyMarkdown } from "../components/LazyMarkdown";
import { useAppStore } from "../stores";
import { navigateToRuntimeChatEntry } from "../utils/runtimeChat";
import styles from "./index.module.less";

const { Sider } = Layout;

const BASE_OPEN_KEYS = ["chat-group", "runtime-group", "settings-group"];

const KEY_TO_PATH: Record<string, string> = {
  chat: "/chat",
  "runtime-center": "/runtime-center",
  industry: "/industry",
  "capability-market": "/capability-market",
  knowledge: "/knowledge",
  reports: "/reports",
  performance: "/performance",
  calendar: "/calendar",
  predictions: "/predictions",
  system: "/settings/system",
  channels: "/settings/channels",
  models: "/settings/models",
  environments: "/settings/environments",
  "agent-config": "/settings/agent-config",
};

const MENU_PARENT_PATHS: Record<string, string[]> = {
  chat: ["chat-group"],
  "runtime-center": ["runtime-group"],
  industry: ["runtime-group"],
  "capability-market": ["runtime-group", "build-subgroup"],
  knowledge: ["runtime-group", "insight-subgroup"],
  reports: ["runtime-group", "insight-subgroup"],
  performance: ["runtime-group", "insight-subgroup"],
  calendar: ["runtime-group", "insight-subgroup"],
  predictions: ["runtime-group", "insight-subgroup"],
  system: ["settings-group"],
  channels: ["settings-group"],
  models: ["settings-group"],
  environments: ["settings-group"],
  "agent-config": ["settings-group"],
};

const UPDATE_MD = `### 更新 Spider Mesh

Spider Mesh 当前以本地 / 私有化部署包的形式分发。
如需更新，请向维护者获取最新安装包，并在安装完成后重启服务。`;

interface SidebarProps {
  selectedKey: string;
}

function defaultOpenKeysFor(selectedKey: string): string[] {
  return Array.from(
    new Set([...BASE_OPEN_KEYS, ...(MENU_PARENT_PATHS[selectedKey] || [])]),
  );
}

export default function Sidebar({ selectedKey }: SidebarProps) {
  const navigate = useNavigate();
  const version = useAppStore((state) => state.version);
  const [collapsed, setCollapsed] = useState(false);
  const [openKeys, setOpenKeys] = useState<string[]>(() =>
    defaultOpenKeysFor(selectedKey),
  );
  const [updateModalOpen, setUpdateModalOpen] = useState(false);
  const [updateMarkdown, setUpdateMarkdown] = useState("");

  useEffect(() => {
    if (!collapsed) {
      setOpenKeys((current) =>
        Array.from(new Set([...current, ...defaultOpenKeysFor(selectedKey)])),
      );
    }
  }, [collapsed, selectedKey]);

  const hasUpdate = false;

  const handleOpenUpdateModal = () => {
    setUpdateMarkdown("");
    setUpdateModalOpen(true);
    setUpdateMarkdown(UPDATE_MD);
  };

  const menuItems: MenuProps["items"] = [
    {
      key: "chat-group",
      label: "对话",
      icon: <MessageSquare size={16} />,
      children: [
        {
          key: "chat",
          label: "聊天前台",
          icon: <MessageSquare size={16} />,
        },
      ],
    },
    {
      key: "runtime-group",
      label: "运行中心",
      icon: <Radar size={16} />,
      children: [
        {
          key: "runtime-center",
          label: "主脑驾驶舱",
          icon: <Radar size={16} />,
        },
        {
          key: "industry",
          label: "行业工作台",
          icon: <Building2 size={16} />,
        },
        {
          key: "build-subgroup",
          label: "构建",
          icon: <Box size={16} />,
          children: [
            {
              key: "capability-market",
              label: "能力市场",
              icon: <Waypoints size={16} />,
            },
          ],
        },
        {
          key: "insight-subgroup",
          label: "洞察",
          icon: <BarChart3 size={16} />,
          children: [
            {
              key: "knowledge",
              label: "知识库",
              icon: <BookOpen size={16} />,
            },
            {
              key: "reports",
              label: "报告",
              icon: <FileText size={16} />,
            },
            {
              key: "performance",
              label: "绩效",
              icon: <Gauge size={16} />,
            },
            {
              key: "calendar",
              label: "日历",
              icon: <CalendarDays size={16} />,
            },
            {
              key: "predictions",
              label: "预测",
              icon: <BarChart3 size={16} />,
            },
          ],
        },
      ],
    },
    {
      key: "settings-group",
      label: "设置",
      icon: <Settings size={16} />,
      children: [
        {
          key: "system",
          label: "系统维护",
          icon: <ShieldCheck size={16} />,
        },
        {
          key: "channels",
          label: "渠道",
          icon: <Wifi size={16} />,
        },
        {
          key: "models",
          label: "模型",
          icon: <Cpu size={16} />,
        },
        {
          key: "environments",
          label: "环境",
          icon: <Box size={16} />,
        },
        {
          key: "agent-config",
          label: "智能体配置",
          icon: <Globe size={16} />,
        },
      ],
    },
  ];

  const handleMenuClick = (event: { key: string }) => {
    if (event.key === "chat") {
      navigateToRuntimeChatEntry(navigate);
      return;
    }
    const path = KEY_TO_PATH[event.key];
    if (path) {
      navigate(path);
    }
  };

  return (
    <Sider
      theme="dark"
      collapsible
      collapsed={collapsed}
      onCollapse={setCollapsed}
      width={252}
      collapsedWidth={64}
      className={`${styles.sidebar} baize-sider`}
      trigger={null}
    >
      <div className={styles.logoWrapper}>
        <div className={styles.brandBlock}>
          <div className={styles.logo}></div>
          {!collapsed ? (
            <div className={styles.brandCopy}>
              <span className={styles.productName}>CoPaw Console</span>
              <span className={styles.productTagline}>Buddy-first runtime command center</span>
            </div>
          ) : null}
        </div>
        {!collapsed ? (
          <div className={styles.version}>
            <span className={styles.statusBadge}>Live</span>
            {version ? <span>{version}</span> : null}
            {version && hasUpdate ? (
              <Badge dot className={styles.updateBadge}>
                <Button
                  type="text"
                  size="small"
                  onClick={handleOpenUpdateModal}
                  className={styles.updateButton}
                >
                  更新
                </Button>
              </Badge>
            ) : null}
          </div>
        ) : null}
      </div>
      <Menu
        selectedKeys={[selectedKey]}
        openKeys={collapsed ? [] : openKeys}
        mode="inline"
        items={menuItems}
        onClick={handleMenuClick}
        onOpenChange={(keys) => setOpenKeys(keys)}
        className={styles.menu}
      />
      <div className={styles.triggerWrapper}>
        <Button
          type="text"
          icon={collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
          onClick={() => setCollapsed(!collapsed)}
          className={styles.triggerButton}
        />
      </div>
      <Modal
        title="版本更新"
        open={updateModalOpen}
        onCancel={() => setUpdateModalOpen(false)}
        footer={null}
        width={600}
        centered
      >
        <div className={styles.updateModalBody}>
          {!updateMarkdown ? (
            <div className={styles.updateModalSpinWrapper}>
              <Spin />
            </div>
          ) : (
            <LazyMarkdown content={updateMarkdown} />
          )}
        </div>
      </Modal>
    </Sider>
  );
}
