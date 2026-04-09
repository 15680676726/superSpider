import { useMemo, useState } from "react";
import { PlusOutlined } from "@ant-design/icons";
import { Card } from "antd";

import { Button } from "@/ui";
import type { ProviderInfo } from "../../../api/types/provider";
import {
  CustomProviderModal,
  LoadingState,
  ModelsSection,
  ProviderCard,
} from "./components";
import styles from "./index.module.less";
import { useProviders } from "./useProviders";

function ModelsPage() {
  const { providers, activeModels, loading, error, fetchAll } = useProviders();
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);
  const [addProviderOpen, setAddProviderOpen] = useState(false);

  const refreshProvidersSilently = () => fetchAll(false);

  const { regularProviders, embeddedProviders } = useMemo(() => {
    const regular: ProviderInfo[] = [];
    const embedded: ProviderInfo[] = [];
    for (const provider of providers) {
      if (provider.is_local) {
        embedded.push(provider);
      } else {
        regular.push(provider);
      }
    }
    return { regularProviders: regular, embeddedProviders: embedded };
  }, [providers]);

  const renderProviderCards = (list: ProviderInfo[]) =>
    list.map((provider) => (
      <ProviderCard
        key={provider.id}
        provider={provider}
        activeModels={activeModels}
        onSaved={refreshProvidersSilently}
        isHover={hoveredCard === provider.id}
        onMouseEnter={() => setHoveredCard(provider.id)}
        onMouseLeave={() => setHoveredCard(null)}
      />
    ));

  return (
    <div className={`${styles.page} page-container`}>
      {loading ? (
        <LoadingState message="加载中..." />
      ) : error ? (
        <LoadingState message={error} error onRetry={fetchAll} />
      ) : (
        <>
          <Card className="baize-page-header">
            <div className="baize-page-header-content">
              <div>
                <h1 className="baize-page-header-title">对话模型</h1>
                <p className="baize-page-header-description">
                  从已授权的提供商中选择当前生效的对话模型。
                </p>
              </div>
            </div>
          </Card>

          <ModelsSection
            providers={providers}
            activeModels={activeModels}
            onSaved={fetchAll}
          />

          <div className={styles.providersBlock}>
            <Card className="baize-page-header">
              <div className="baize-page-header-content">
                <div>
                  <h1 className="baize-page-header-title">提供商</h1>
                  <p className="baize-page-header-description">
                    为每个提供商配置接口密钥和服务地址。
                  </p>
                </div>
                <div className="baize-page-header-actions">
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => setAddProviderOpen(true)}
                    className="baize-btn"
                  >
                    添加提供商
                  </Button>
                </div>
              </div>
            </Card>

            {regularProviders.length > 0 ? (
              <div className={styles.providerGroup}>
                <div className={styles.providerCards}>
                  {renderProviderCards(regularProviders)}
                </div>
              </div>
            ) : null}

            {embeddedProviders.length > 0 ? (
              <div className={styles.providerGroup}>
                <h4 className={styles.providerGroupTitle}>嵌入式（进程内）</h4>
                <div className={styles.providerCards}>
                  {renderProviderCards(embeddedProviders)}
                </div>
              </div>
            ) : null}
          </div>

          <CustomProviderModal
            open={addProviderOpen}
            onClose={() => setAddProviderOpen(false)}
            onSaved={fetchAll}
          />
        </>
      )}
    </div>
  );
}

export default ModelsPage;
