import { useMemo, useState } from "react";
import { Button } from "@/ui";
import { PlusOutlined } from "@ant-design/icons";
import { useProviders } from "./useProviders";
import {
  Card,
} from "antd";
import {
  LoadingState,
  ProviderCard,
  ModelsSection,
  CustomProviderModal,
} from "./components";
import type { ProviderInfo } from "../../../api/types/provider";
import styles from "./index.module.less";

/* ------------------------------------------------------------------ */
/* Main Page                                                           */
/* ------------------------------------------------------------------ */

function ModelsPage() {
  const { providers, activeModels, loading, error, fetchAll } = useProviders();
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);
  const [addProviderOpen, setAddProviderOpen] = useState(false);

  const refreshProvidersSilently = () => fetchAll(false);

  const { regularProviders, embeddedProviders } = useMemo(() => {
    const regular: ProviderInfo[] = [];
    const embedded: ProviderInfo[] = [];
    for (const p of providers) {
      if (p.is_local) embedded.push(p);
      else regular.push(p);
    }
    return { regularProviders: regular, embeddedProviders: embedded };
  }, [providers]);

  const handleMouseEnter = (providerId: string) => {
    setHoveredCard(providerId);
  };

  const handleMouseLeave = () => {
    setHoveredCard(null);
  };

  const renderProviderCards = (list: ProviderInfo[]) =>
    list.map((provider) => (
      <ProviderCard
        key={provider.id}
        provider={provider}
        activeModels={activeModels}
        onSaved={refreshProvidersSilently}
        isHover={hoveredCard === provider.id}
        onMouseEnter={() => handleMouseEnter(provider.id)}
        onMouseLeave={handleMouseLeave}
      />
    ));

  return (
    <div className={`${styles.page} page-container`}>
      {loading ? (
        <LoadingState message={"加载中..."} />
      ) : error ? (
        <LoadingState message={error} error onRetry={fetchAll} />
      ) : (
        <>
          <Card className="baize-page-header">
            <div className="baize-page-header-content">
              <div>
                <h1 className="baize-page-header-title">对话模型</h1>
                <p className="baize-page-header-description">
                  从已授权的提供商中选择活动的对话模型。
                </p>
              </div>
            </div>
          </Card>
          <ModelsSection
            providers={providers}
            activeModels={activeModels}
            onSaved={fetchAll}
          />

          {/* ---- Providers Section (below) ---- */}
          <div className={styles.providersBlock}>
          <Card className="baize-page-header">
            <div className="baize-page-header-content">
              <div>
                <h1 className="baize-page-header-title">提供商</h1>
                <p className="baize-page-header-description">
                  为每个提供方配置接口密钥和服务端点。
                </p>
              </div>
              <div className="baize-page-header-actions">
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setAddProviderOpen(true)}
                  className="baize-btn"
                >
                  添加提供方
                </Button>
              </div>
            </div>
          </Card>

            {regularProviders.length > 0 && (
              <div className={styles.providerGroup}>
                <div className={styles.providerCards}>
                  {renderProviderCards(regularProviders)}
                </div>
              </div>
            )}

            {embeddedProviders.length > 0 && (
              <div className={styles.providerGroup}>
                <h4 className={styles.providerGroupTitle}>
                  {"嵌入式（进程内）"}
                </h4>
                <div className={styles.providerCards}>
                  {renderProviderCards(embeddedProviders)}
                </div>
              </div>
            )}
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
