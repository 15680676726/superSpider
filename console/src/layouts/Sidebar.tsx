import {
  Badge,
  Button,
  Layout,
  Menu,
  Modal,
  Spin,
  message,
  type MenuProps,
} from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  Box,
  Briefcase,
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
import api from "../api";
import sessionApi from "../pages/Chat/sessionApi";
import { useAppStore } from "../stores";
import {
  buildIndustryRoleChatBinding,
  openRuntimeChat,
  resolveIndustryExecutionCoreRole,
} from "../utils/runtimeChat";
import styles from "./index.module.less";

const { Sider } = Layout;

const BASE_OPEN_KEYS = ["chat-group", "runtime-group", "settings-group"];

const KEY_TO_PATH: Record<string, string> = {
  chat: "/chat",
  "runtime-center": "/runtime-center",
  agents: "/agents",
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
  agents: ["runtime-group"],
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

const UPDATE_MD = `### Update Spider Mesh

Spider Mesh is distributed as a local/private deployment bundle.
If you need an update, request the latest package from the maintainer and restart the service after installation.`;

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
      label: "Chat",
      icon: <MessageSquare size={16} />,
      children: [
        {
          key: "chat",
          label: "Chat",
          icon: <MessageSquare size={16} />,
        },
      ],
    },
    {
      key: "runtime-group",
      label: "Runtime",
      icon: <Radar size={16} />,
      children: [
        {
          key: "runtime-center",
          label: "Runtime Center",
          icon: <Radar size={16} />,
        },
        {
          key: "agents",
          label: "Agents",
          icon: <Briefcase size={16} />,
        },
        {
          key: "industry",
          label: "Industry",
          icon: <Building2 size={16} />,
        },
        {
          key: "build-subgroup",
          label: "Build",
          icon: <Box size={16} />,
          children: [
            {
              key: "capability-market",
              label: "Capability Market",
              icon: <Waypoints size={16} />,
            },
          ],
        },
        {
          key: "insight-subgroup",
          label: "Insights",
          icon: <BarChart3 size={16} />,
          children: [
            {
              key: "knowledge",
              label: "Knowledge",
              icon: <BookOpen size={16} />,
            },
            {
              key: "reports",
              label: "Reports",
              icon: <FileText size={16} />,
            },
            {
              key: "performance",
              label: "Performance",
              icon: <Gauge size={16} />,
            },
            {
              key: "calendar",
              label: "Calendar",
              icon: <CalendarDays size={16} />,
            },
            {
              key: "predictions",
              label: "Predictions",
              icon: <BarChart3 size={16} />,
            },
          ],
        },
      ],
    },
    {
      key: "settings-group",
      label: "Settings",
      icon: <Settings size={16} />,
      children: [
        {
          key: "system",
          label: "System",
          icon: <ShieldCheck size={16} />,
        },
        {
          key: "channels",
          label: "Channels",
          icon: <Wifi size={16} />,
        },
        {
          key: "models",
          label: "Models",
          icon: <Cpu size={16} />,
        },
        {
          key: "environments",
          label: "Environments",
          icon: <Box size={16} />,
        },
        {
          key: "agent-config",
          label: "Agent Config",
          icon: <Globe size={16} />,
        },
      ],
    },
  ];

  const openPreferredChatEntry = async (): Promise<void> => {
    const activeThreadId = sessionApi.getActiveThreadId();
    if (activeThreadId) {
      navigate(`/chat?threadId=${encodeURIComponent(activeThreadId)}`);
      return;
    }
    try {
      const instances = await api.listIndustryInstances(5);
      const candidates = (Array.isArray(instances) ? instances : []).filter(
        (instance) => resolveIndustryExecutionCoreRole(instance),
      );
      if (candidates.length === 1) {
        const executionCoreRole = resolveIndustryExecutionCoreRole(candidates[0]);
        if (executionCoreRole) {
          await openRuntimeChat(
            buildIndustryRoleChatBinding(candidates[0], executionCoreRole),
            navigate,
          );
          return;
        }
      }
    } catch (error) {
      message.warning(error instanceof Error ? error.message : String(error));
    }
    navigate("/chat");
  };

  const handleMenuClick = (event: { key: string }) => {
    if (event.key === "chat") {
      void openPreferredChatEntry();
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
      width={240}
      collapsedWidth={52}
      className={`${styles.sidebar} baize-sider`}
      trigger={null}
    >
      <div className={styles.logoWrapper}>
        <div className={styles.logo}></div>
        <div className={styles.version}>
          {version ? <span>{version}</span> : null}
          {version && hasUpdate ? (
            <Badge dot className={styles.updateBadge}>
              <Button
                type="text"
                size="small"
                onClick={handleOpenUpdateModal}
                className={styles.updateButton}
              >
                Update
              </Button>
            </Badge>
          ) : null}
        </div>
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
        title="Version Update"
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
