import { Suspense, lazy } from "react";
import { Layout, Spin } from "antd";
import { Route, Routes, useLocation } from "react-router-dom";
import { routes, resolveSelectedKey } from "../../routes";
import styles from "../index.module.less";

const Sidebar = lazy(() => import("../Sidebar"));
const Header = lazy(() => import("../Header"));
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

  return (
    <Layout className={`baize-layout ${styles.mainLayout}`}>
      <Suspense fallback={<ShellFallback width={240} />}>
        <Sidebar selectedKey={selectedKey} />
      </Suspense>
      <Layout className="baize-layout-content" style={{ background: "transparent" }}>
        <Suspense fallback={<ShellFallback minHeight={64} />}>
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
    </Layout>
  );
}
