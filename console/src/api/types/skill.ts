export interface SkillSpec {
  name: string;
  content: string;
  source: string;
  path: string;
  enabled?: boolean;
}

export interface HubSkillSpec {
  slug: string;
  name: string;
  description: string;
  version: string;
  source_url: string;
  source_label?: string;
}

export interface CuratedSkillCatalogSource {
  source_id: string;
  label: string;
  source_kind: "skillhub-curated";
  query?: string;
  max_items?: number;
  notes: string[];
  allowed_bundle_hosts: string[];
}

export interface CuratedSkillCatalogEntry {
  candidate_id: string;
  source_id: string;
  source_label: string;
  source_kind: "skillhub-curated";
  source_repo_url: string;
  discovery_kind: "skillhub-preset" | "skillhub-search" | "manifest";
  manifest_status: "skillhub-curated" | "verified";
  title: string;
  description: string;
  bundle_url: string;
  version: string;
  install_name: string;
  tags: string[];
  capability_tags: string[];
  review_required: boolean;
  review_summary: string;
  review_notes: string[];
  routes: Record<string, string>;
}

export interface CuratedSkillCatalogSearchResponse {
  sources: CuratedSkillCatalogSource[];
  items: CuratedSkillCatalogEntry[];
  total: number;
  warnings: string[];
}

// Legacy Skill interface for backward compatibility
export interface Skill {
  id: string;
  name: string;
  description: string;
  function_name: string;
  enabled: boolean;
  version: string;
  tags: string[];
  created_at: number;
  updated_at: number;
}
