import { Suspense, lazy, useEffect } from "react";
import { Layout, Spin } from "antd";
import { Route, Routes, useLocation } from "react-router-dom";
import { routes, resolveSelectedKey } from "../../routes";
import {
  resolveLikelyNextRoutePaths,
  scheduleRoutePreload,
} from "../../routes/preload";
import Header from "../Header";
import RightPanel from "../RightPanel";
import Sidebar from "../Sidebar";
import styles from "../index.module.less";

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
      <Sidebar selectedKey={selectedKey} />

      {/* ---- 中间主内容 ---- */}
      <Layout
        className="baize-layout-content"
        style={{ background: "transparent", flex: 1, minWidth: 0 }}
      >
        <Header selectedKey={selectedKey} />
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
      <RightPanel />
    </div>
  );
}
