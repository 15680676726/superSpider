import { Navigate } from "react-router-dom";
import { lazyWithPreload } from "./preload";

const Chat = lazyWithPreload(() => import("../pages/Chat"));
const BuddyOnboardingPage = lazyWithPreload(() => import("../pages/BuddyOnboarding"));
const AgentConfigPage = lazyWithPreload(() => import("../pages/Agent/Config"));
const RuntimeCenterPage = lazyWithPreload(() => import("../pages/RuntimeCenter"));
const IndustryPage = lazyWithPreload(() => import("../pages/Industry"));
const PredictionsPage = lazyWithPreload(() => import("../pages/Predictions"));
const KnowledgePage = lazyWithPreload(() => import("../pages/Knowledge"));
const ReportsPage = lazyWithPreload(() => import("../pages/Reports"));
const PerformancePage = lazyWithPreload(() => import("../pages/Performance"));
const CalendarPage = lazyWithPreload(() => import("../pages/Calendar"));
const ChannelsPage = lazyWithPreload(() => import("../pages/Settings/Channels"));
const ModelsPage = lazyWithPreload(() => import("../pages/Settings/Models"));
const EnvironmentsPage = lazyWithPreload(() => import("../pages/Settings/Environments"));
const CapabilityMarketPage = lazyWithPreload(() => import("../pages/CapabilityMarket"));
const SystemSettingsPage = lazyWithPreload(() => import("../pages/Settings/System"));

export interface RouteConfig {
  path: string;
  element: React.ReactNode;
  menuKey?: string;
  preload?: () => Promise<unknown>;
}

export const routes: RouteConfig[] = [
  { path: "/", element: <Navigate to="/buddy-onboarding" replace /> },
  {
    path: "/buddy-onboarding",
    element: <BuddyOnboardingPage />,
    menuKey: "chat",
    preload: BuddyOnboardingPage.preload,
  },
  {
    path: "/chat",
    element: <Chat />,
    menuKey: "chat",
    preload: Chat.preload,
  },
  {
    path: "/runtime-center",
    element: <RuntimeCenterPage />,
    menuKey: "runtime-center",
    preload: RuntimeCenterPage.preload,
  },
  {
    path: "/industry",
    element: <IndustryPage />,
    menuKey: "industry",
    preload: IndustryPage.preload,
  },
  {
    path: "/predictions",
    element: <PredictionsPage />,
    menuKey: "predictions",
    preload: PredictionsPage.preload,
  },
  {
    path: "/knowledge",
    element: <KnowledgePage />,
    menuKey: "knowledge",
    preload: KnowledgePage.preload,
  },
  {
    path: "/reports",
    element: <ReportsPage />,
    menuKey: "reports",
    preload: ReportsPage.preload,
  },
  {
    path: "/performance",
    element: <PerformancePage />,
    menuKey: "performance",
    preload: PerformancePage.preload,
  },
  {
    path: "/calendar",
    element: <CalendarPage />,
    menuKey: "calendar",
    preload: CalendarPage.preload,
  },
  {
    path: "/capability-market",
    element: <CapabilityMarketPage />,
    menuKey: "capability-market",
    preload: CapabilityMarketPage.preload,
  },
  { path: "/settings", element: <Navigate to="/settings/system" replace /> },
  {
    path: "/settings/system",
    element: <SystemSettingsPage />,
    menuKey: "system",
    preload: SystemSettingsPage.preload,
  },
  {
    path: "/settings/channels",
    element: <ChannelsPage />,
    menuKey: "channels",
    preload: ChannelsPage.preload,
  },
  {
    path: "/settings/models",
    element: <ModelsPage />,
    menuKey: "models",
    preload: ModelsPage.preload,
  },
  {
    path: "/settings/environments",
    element: <EnvironmentsPage />,
    menuKey: "environments",
    preload: EnvironmentsPage.preload,
  },
  {
    path: "/settings/agent-config",
    element: <AgentConfigPage />,
    menuKey: "agent-config",
    preload: AgentConfigPage.preload,
  },
  { path: "*", element: <Navigate to="/runtime-center" replace /> },
];

const PATHNAME_TO_KEY: Array<[string, string]> = [
  ["/capability-market", "capability-market"],
  ["/settings/channels", "channels"],
  ["/settings/system", "system"],
  ["/settings/models", "models"],
  ["/settings/environments", "environments"],
  ["/settings/agent-config", "agent-config"],
  ["/industry", "industry"],
  ["/predictions", "predictions"],
  ["/knowledge", "knowledge"],
  ["/reports", "reports"],
  ["/performance", "performance"],
  ["/calendar", "calendar"],
  ["/chat", "chat"],
  ["/buddy-onboarding", "chat"],
  ["/runtime-center", "runtime-center"],
];

export function resolveSelectedKey(pathname: string, search: string = ""): string {
  void search;
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
