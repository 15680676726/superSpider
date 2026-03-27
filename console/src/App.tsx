import { Suspense, lazy } from "react";

import { App as AntdApp, ConfigProvider } from "antd";
import zh_CN from "antd/locale/zh_CN";
import { BrowserRouter, useLocation } from "react-router-dom";

import { baizeTheme } from "./theme/baizeTheme";
import { PageErrorBoundary } from "./components/PageErrorBoundary";
import { NetworkOfflineBanner } from "./components/NetworkOfflineBanner";
import "./styles/layout.css";
import "./styles/form-override.css";

const MainLayout = lazy(() => import("./layouts/MainLayout"));

function RoutedShell() {
  const location = useLocation();
  const resetKey = `${location.pathname}${location.search}${location.hash}`;

  return (
    <PageErrorBoundary resetKey={resetKey}>
      <Suspense fallback={<div style={{ minHeight: "100vh" }} />}>
        <MainLayout />
      </Suspense>
    </PageErrorBoundary>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ConfigProvider
        {...baizeTheme}
        locale={zh_CN}
        prefixCls="baize"
      >
        <AntdApp>
          <NetworkOfflineBanner />
          <RoutedShell />
        </AntdApp>
      </ConfigProvider>
    </BrowserRouter>
  );
}

export default App;
