const BRAND_REPLACEMENTS: Array<[RegExp, string]> = [
  [/白泽执行中枢/g, "超级伙伴主脑"],
  [/Spider Mesh 执行中枢/g, "超级伙伴主脑"],
  [/白泽治理中枢/g, "超级伙伴治理中枢"],
  [/Spider Mesh 治理中枢/g, "超级伙伴治理中枢"],
  [/白泽调度中枢/g, "超级伙伴调度中枢"],
  [/Spider Mesh 调度中枢/g, "超级伙伴调度中枢"],
  [/白泽行业团队/g, "超级伙伴行业身份"],
  [/Spider Mesh 行业身份/g, "超级伙伴行业身份"],
  [/Baize Runtime Center/g, "超级伙伴主脑驾驶舱"],
  [/Spider Mesh Runtime Center/g, "超级伙伴主脑驾驶舱"],
  [/Spider Mesh 主脑/g, "超级伙伴主脑"],
  [/\bSpider Mesh\b/g, "超级伙伴"],
  [/\bBaize\b/g, "超级伙伴"],
  [/白泽/g, "超级伙伴"],
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
