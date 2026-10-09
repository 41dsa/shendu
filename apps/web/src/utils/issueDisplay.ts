/** 与 services/api/app/domain/essay.py ESSAY_ISSUE_TAGS 对齐 */

export const ESSAY_ISSUE_TAGS: { code: string; label: string; keywords: string[] }[] = [
  { code: "Q21", label: "立意偏差", keywords: ["立意", "偏题", "题意", "审题"] },
  { code: "Q25", label: "结构失衡", keywords: ["结构", "层次", "递进", "重复", "交叉"] },
  { code: "Q22", label: "分论点弱", keywords: ["分论点", "论点弱"] },
  { code: "Q24", label: "论证不足", keywords: ["论证", "因果", "分析不足", "对策为主"] },
  { code: "Q23", label: "论据不足", keywords: ["论据", "案例", "数据", "素材", "材料", "联系实际"] },
  { code: "Q17", label: "语言不规范", keywords: ["语言", "口号", "模板", "病句", "错别字"] },
  { code: "Q20", label: "字数问题", keywords: ["字数", "篇幅", "不足", "达标"] },
];

const GENERIC_ISSUE_TAG = /^问题\s*\d+$/i;

function inferFromText(text: string): { code: string; label: string } | null {
  const t = text.trim();
  if (!t) return null;
  for (const row of ESSAY_ISSUE_TAGS) {
    if (row.keywords.some((kw) => t.includes(kw))) {
      return { code: row.code, label: row.label };
    }
  }
  return null;
}

function labelForCode(code: string): string | null {
  const c = code.toUpperCase();
  return ESSAY_ISSUE_TAGS.find((r) => r.code === c)?.label ?? null;
}

/** 问题类型短标签（前端不展示 Q 编号，仅展示名称） */
export function issueBadgeText(item: {
  tag?: string | null;
  explanation?: string | null;
}): string {
  const tag = (item.tag ?? "").trim();
  const explanation = (item.explanation ?? "").trim();
  const qMatch = tag.match(/^(Q\d+)\s*(.*)$/i);
  if (qMatch) {
    const named = labelForCode(qMatch[1]);
    if (named) return named;
    const rest = qMatch[2]?.trim();
    if (rest) return rest;
  }
  if (tag && !GENERIC_ISSUE_TAG.test(tag) && !/^Q\d+/i.test(tag) && tag.length <= 16) {
    return tag;
  }
  const inferred = inferFromText(`${explanation} ${tag}`);
  if (inferred) return inferred.label;
  const clause = (explanation || tag).split(/[，,。；;]/)[0]?.trim() ?? "";
  if (clause.length > 0 && clause.length <= 14) return clause;
  return "作答问题";
}

/** 正文中的问题分析（长说明） */
export function issueAnalysisText(item: {
  tag?: string | null;
  explanation?: string | null;
}): string {
  const explanation = (item.explanation ?? "").trim();
  const tag = (item.tag ?? "").trim();
  if (explanation) return explanation;
  if (tag && !GENERIC_ISSUE_TAG.test(tag) && !/^Q\d+/i.test(tag)) return tag;
  return "（暂无详细说明）";
}
