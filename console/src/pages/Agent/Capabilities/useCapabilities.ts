import { useEffect, useState } from "react";
import { message } from "@/ui";
import { capabilityMarketApi } from "../../../api/modules/capabilityMarket";
import type { CapabilityMount, CapabilitySummary } from "../../../api/types";

export function useCapabilities() {
  const [capabilities, setCapabilities] = useState<CapabilityMount[]>([]);
  const [summary, setSummary] = useState<CapabilitySummary | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [capabilityList, summaryPayload] = await Promise.all([
        capabilityMarketApi.listCapabilityMarketCapabilities().catch(() => []),
        capabilityMarketApi.getCapabilityMarketSummary().catch(() => null),
      ]);
      setCapabilities(capabilityList ?? []);
      if (summaryPayload) {
        setSummary(summaryPayload);
      }
    } catch (error) {
      console.error("Failed to load capabilities", error);
      message.error("加载能力列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return {
    capabilities,
    summary,
    loading,
    reload: load,
  };
}
