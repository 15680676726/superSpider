const BRAND_REPLACEMENTS: Array<[RegExp, string]> = [
  [/白泽执行中枢/g, "Spider Mesh 主脑"],
  [/Spider Mesh 执行中枢/g, "Spider Mesh 主脑"],
  [/白泽治理中枢/g, "Spider Mesh 治理中枢"],
  [/白泽调度中枢/g, "Spider Mesh 调度中枢"],
  [/白泽行业团队/g, "Spider Mesh 行业身份"],
  [/Baize Runtime Center/g, "Spider Mesh Runtime Center"],
  [/\bBaize\b/g, "Spider Mesh"],
  [/白泽/g, "Spider Mesh"],
];

export function normalizeSpiderMeshBrand(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  let normalized = String(value);
  for (const [pattern, replacement] of BRAND_REPLACEMENTS) {
    normalized = normalized.replace(pattern, replacement);
  }
  return normalized;
}
