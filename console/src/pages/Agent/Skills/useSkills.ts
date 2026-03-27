import { useState, useEffect } from "react";
import { message, Modal } from "@/ui";
import {
  capabilityMutationRequiresConfirmation,
  type CapabilityMutationResponse,
} from "../../../api/modules/capability";
import { capabilityMarketApi } from "../../../api/modules/capabilityMarket";
import type { CapabilityMount, SkillSpec } from "../../../api/types";

export type SkillCapabilityView = SkillSpec & {
  capability?: CapabilityMount;
};

function confirmationMessage(result: CapabilityMutationResponse): string {
  return result.decision_request_id
    ? `等待确认：${result.decision_request_id}`
    : "等待确认";
}

export function useSkills() {
  const [skills, setSkills] = useState<SkillCapabilityView[]>([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);

  const fetchSkills = async () => {
    setLoading(true);
    try {
      const [data, capabilities] = await Promise.all([
        capabilityMarketApi.listCapabilityMarketSkills(),
        capabilityMarketApi
          .listCapabilityMarketCapabilities({ kind: "skill-bundle" })
          .catch(() => []),
      ]);
      if (data) {
        setSkills(mergeSkillsWithCapabilities(data, capabilities));
      }
    } catch (error) {
      console.error("Failed to load skills", error);
      message.error("加载技能列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const loadSkills = async () => {
      await fetchSkills();
    };

    if (mounted) {
      void loadSkills();
    }

    return () => {
      mounted = false;
    };
  }, []);

  const createSkill = async (name: string, content: string) => {
    try {
      await capabilityMarketApi.createCapabilityMarketSkill({ name, content });
      message.success("技能创建成功");
      await fetchSkills();
      return true;
    } catch (error) {
      console.error("Failed to save skill", error);
      message.error("创建技能失败");
      return false;
    }
  };

  const importFromHub = async (input: string) => {
    const text = (input || "").trim();
    if (!text) {
      message.warning("请输入技能地址");
      return false;
    }
    if (!text.startsWith("http://") && !text.startsWith("https://")) {
      message.warning("技能地址格式不正确");
      return false;
    }
    try {
      setImporting(true);
      const payload = { bundle_url: text, enable: true, overwrite: false };
      const result = await capabilityMarketApi.installCapabilityMarketHub(payload);
      if (result?.installed) {
        message.success(`技能导入成功：${result.name}`);
        await fetchSkills();
        return true;
      }
      message.error("导入技能失败");
      return false;
    } catch (error) {
      console.error("Failed to import skill from hub", error);
      message.error("导入技能失败");
      return false;
    } finally {
      setImporting(false);
    }
  };

  const toggleEnabled = async (skill: SkillSpec) => {
    try {
      const capabilityId = `skill:${skill.name}`;
      const result = await capabilityMarketApi.toggleCapabilityMarketCapability(
        capabilityId,
      );
      if (capabilityMutationRequiresConfirmation(result)) {
        message.warning(confirmationMessage(result));
        return true;
      }
      if (result?.toggled) {
        setSkills((prev) =>
          prev.map((s) =>
            s.name === skill.name ? { ...s, enabled: !skill.enabled } : s,
          ),
        );
        message.success(
          result.summary ||
            (skill.enabled
              ? "技能已停用"
              : "技能已启用"),
        );
        return true;
      }
      message.error(result?.error || result?.summary || "切换技能状态失败");
      return false;
    } catch (error) {
      console.error("Failed to toggle skill", error);
      message.error("切换技能状态失败");
      return false;
    }
  };

  const deleteSkill = async (skill: SkillSpec) => {
    const confirmed = await new Promise<boolean>((resolve) => {
      Modal.confirm({
        title: "删除技能",
        content: `确定要删除技能“${skill.name}”吗？此操作不可恢复。`,
        okText: "删除",
        okType: "danger",
        cancelText: "取消",
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });

    if (!confirmed) return false;

    try {
      const capabilityId = `skill:${skill.name}`;
      const result = await capabilityMarketApi.deleteCapabilityMarketCapability(
        capabilityId,
      );
      if (capabilityMutationRequiresConfirmation(result)) {
        message.warning(confirmationMessage(result));
        return true;
      }
      if (result?.deleted) {
        message.success(result.summary || "技能已删除");
        await fetchSkills();
        return true;
      }
      message.error(result?.error || result?.summary || "删除技能失败");
      return false;
    } catch (error) {
      console.error("Failed to delete skill", error);
      message.error("删除技能失败");
      return false;
    }
  };

  return {
    skills,
    loading,
    importing,
    createSkill,
    importFromHub,
    toggleEnabled,
    deleteSkill,
  };
}

function mergeSkillsWithCapabilities(
  skills: SkillSpec[],
  capabilities: CapabilityMount[],
): SkillCapabilityView[] {
  const capabilityMap = new Map(
    capabilities.map((capability) => [capability.id, capability]),
  );
  return skills.map((skill) => ({
    ...skill,
    capability: capabilityMap.get(`skill:${skill.name}`),
  }));
}
