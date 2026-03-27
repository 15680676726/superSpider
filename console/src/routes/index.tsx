import { lazy } from "react";
import { Navigate } from "react-router-dom";

const Chat = lazy(() => import("../pages/Chat"));
const AgentConfigPage = lazy(() => import("../pages/Agent/Config"));
const RuntimeCenterPage = lazy(() => import("../pages/RuntimeCenter"));
const AgentWorkbenchPage = lazy(() => import("../pages/AgentWorkbench"));
const IndustryPage = lazy(() => import("../pages/Industry"));
const PredictionsPage = lazy(() => import("../pages/Predictions"));
const KnowledgePage = lazy(() => import("../pages/Knowledge"));
const ReportsPage = lazy(() => import("../pages/Reports"));
const PerformancePage = lazy(() => import("../pages/Performance"));
const CalendarPage = lazy(() => import("../pages/Calendar"));
const ChannelsPage = lazy(() => import("../pages/Settings/Channels"));
const ModelsPage = lazy(() => import("../pages/Settings/Models"));
const EnvironmentsPage = lazy(() => import("../pages/Settings/Environments"));
const CapabilityMarketPage = lazy(() => import("../pages/CapabilityMarket"));
const SystemSettingsPage = lazy(() => import("../pages/Settings/System"));

export interface RouteConfig {
  path: string;
  element: React.ReactNode;
  menuKey?: string;
}

export const routes: RouteConfig[] = [
  { path: "/", element: <Navigate to="/runtime-center" replace /> },
  { path: "/chat", element: <Chat />, menuKey: "chat" },
  {
    path: "/runtime-center",
    element: <RuntimeCenterPage />,
    menuKey: "runtime-center",
  },
  { path: "/industry", element: <IndustryPage />, menuKey: "industry" },
  { path: "/predictions", element: <PredictionsPage />, menuKey: "predictions" },
  { path: "/knowledge", element: <KnowledgePage />, menuKey: "knowledge" },
  { path: "/reports", element: <ReportsPage />, menuKey: "reports" },
  { path: "/performance", element: <PerformancePage />, menuKey: "performance" },
  { path: "/calendar", element: <CalendarPage />, menuKey: "calendar" },
  {
    path: "/capability-market",
    element: <CapabilityMarketPage />,
    menuKey: "capability-market",
  },
  { path: "/settings", element: <Navigate to="/settings/system" replace /> },
  {
    path: "/settings/system",
    element: <SystemSettingsPage />,
    menuKey: "system",
  },
  {
    path: "/settings/channels",
    element: <ChannelsPage />,
    menuKey: "channels",
  },
  { path: "/settings/models", element: <ModelsPage />, menuKey: "models" },
  {
    path: "/settings/environments",
    element: <EnvironmentsPage />,
    menuKey: "environments",
  },
  {
    path: "/settings/agent-config",
    element: <AgentConfigPage />,
    menuKey: "agent-config",
  },
  { path: "/agents", element: <AgentWorkbenchPage />, menuKey: "agents" },
  { path: "*", element: <Navigate to="/runtime-center" replace /> },
];

const PATHNAME_TO_KEY: Array<[string, string]> = [
  ["/capability-market", "capability-market"],
  ["/settings/channels", "channels"],
  ["/settings/system", "system"],
  ["/settings/models", "models"],
  ["/settings/environments", "environments"],
  ["/settings/agent-config", "agent-config"],
  ["/agents", "agents"],
  ["/industry", "industry"],
  ["/predictions", "predictions"],
  ["/knowledge", "knowledge"],
  ["/reports", "reports"],
  ["/performance", "performance"],
  ["/calendar", "calendar"],
  ["/chat", "chat"],
  ["/runtime-center", "runtime-center"],
];

export function resolveSelectedKey(pathname: string, _search: string = ""): string {
  if (pathname.startsWith("/capability-market")) {
    return "capability-market";
  }
  for (const [prefix, key] of PATHNAME_TO_KEY) {
    if (pathname.startsWith(prefix)) {
      return key;
    }
  }
  return "runtime-center";
}
