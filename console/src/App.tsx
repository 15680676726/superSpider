import { App as AntdApp, ConfigProvider } from "antd";
import zh_CN from "antd/locale/zh_CN";
import { BrowserRouter, useLocation } from "react-router-dom";

import { baizeTheme } from "./theme/baizeTheme";
import { PageErrorBoundary } from "./components/PageErrorBoundary";
import { NetworkOfflineBanner } from "./components/NetworkOfflineBanner";
import MainLayout from "./layouts/MainLayout";
import "./styles/layout.css";
import "./styles/form-override.css";

function RoutedShell() {
  const location = useLocation();
  const resetKey = `${location.pathname}${location.search}${location.hash}`;

  return (
    <PageErrorBoundary resetKey={resetKey}>
      <MainLayout />
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
