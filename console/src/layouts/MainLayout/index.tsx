import { Suspense, lazy, useEffect } from "react";
import { Layout, Spin } from "antd";
import { Route, Routes, useLocation } from "react-router-dom";
import { routes, resolveSelectedKey } from "../../routes";
import {
  resolveLikelyNextRoutePaths,
  scheduleRoutePreload,
} from "../../routes/preload";
import styles from "../index.module.less";

const Sidebar = lazy(() => import("../Sidebar"));
const Header = lazy(() => import("../Header"));
const RightPanel = lazy(() => import("../RightPanel"));
const ConsoleCronBubble = lazy(() => import("../../components/ConsoleCronBubble"));
const RuntimeExecutionLauncher = lazy(
  () => import("../../components/RuntimeExecutionLauncher"),
);

const { Content } = Layout;

function RouteFallback() {
  return (
    <div
      style={{
        minHeight: 320,
        display: "grid",
        placeItems: "center",
      }}
    >
      <Spin size="large" />
    </div>
  );
}

function ShellFallback({ minHeight = 0, width = "100%" }: {
  minHeight?: number;
  width?: number | string;
}) {
  return (
    <div
      style={{
        width,
        minHeight,
      }}
    />
  );
}

export default function MainLayout() {
  const location = useLocation();
  const selectedKey = resolveSelectedKey(location.pathname, location.search);

  useEffect(() => {
    return scheduleRoutePreload(routes, resolveLikelyNextRoutePaths(location.pathname));
  }, [location.pathname]);

  return (
    /* 最外层用 flex row 实现三栏 */
    <div
      className={`baize-layout ${styles.mainLayout}`}
      style={{ display: "flex", flexDirection: "row", height: "100vh", overflow: "hidden" }}
    >
      {/* ---- 左侧导航 ---- */}
      <Suspense fallback={<ShellFallback width={252} />}>
        <Sidebar selectedKey={selectedKey} />
      </Suspense>

      {/* ---- 中间主内容 ---- */}
      <Layout
        className="baize-layout-content"
        style={{ background: "transparent", flex: 1, minWidth: 0 }}
      >
        <Suspense fallback={<ShellFallback minHeight={60} />}>
          <Header selectedKey={selectedKey} />
        </Suspense>
        <Content className={styles.pageContainer}>
          <Suspense fallback={null}>
            <ConsoleCronBubble />
          </Suspense>
          <Suspense fallback={null}>
            <RuntimeExecutionLauncher />
          </Suspense>
          <div
            className={styles.pageContent}
            style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}
          >
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                {routes.map((route) => (
                  <Route key={route.path} path={route.path} element={route.element} />
                ))}
              </Routes>
            </Suspense>
          </div>
        </Content>
      </Layout>

      {/* ---- 右侧智体面板 ---- */}
      <Suspense fallback={<ShellFallback width={260} />}>
        <RightPanel />
      </Suspense>
    </div>
  );
}
