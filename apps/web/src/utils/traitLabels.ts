/** PRD V1 八大 Trait 与 L0–L4 档位 — 管理端/报告共用中文名 */

export const TRAIT_LABELS: Record<string, string> = {
  T1: "审题与任务完成",
  T2: "立意与中心论点",
  T3: "分论点与结构",
  T4: "材料转化与论据",
  T5: "论证完整性",
  T6: "分析深度",
  T7: "对策与治理思维",
  T8: "语言与规范",
};

export const LEVEL_LABELS: Record<string, string> = {
  L4: "L4 强",
  L3: "L3 较强",
  L2: "L2 一般",
  L1: "L1 较弱",
  L0: "L0 严重缺失",
};

export const LEVEL_HINT =
  "档位 L0～L4 表示该维度能力由低到高：L0 严重缺失 → L1 较弱 → L2 一般 → L3 较强 → L4 强。";

export const TRAIT_HINT =
  "维度（Trait）即八大诊断项：审题、立意、结构、材料、论证、分析、对策、语言；B 档参与估分，C 档仅诊断。";

export function traitSelectLabel(traitId: string): string {
  const name = TRAIT_LABELS[traitId];
  return name ? `${traitId} ${name}` : traitId;
}

export function levelSelectLabel(level: string): string {
  return LEVEL_LABELS[level] ?? level;
}

export function formatQuestionLabel(questionId: string | null | undefined): string {
  if (!questionId) return "—";
  if (questionId === "sys-user-essay") return "用户自备题";
  if (questionId.startsWith("demo-")) return "演示题库";
  return questionId;
}

/** 列表紧凑展示：审题 L4、立意 L3 … */
export const TRAIT_SHORT: Record<string, string> = {
  T1: "审题",
  T2: "立意",
  T3: "结构",
  T4: "材料",
  T5: "论证",
  T6: "分析",
  T7: "对策",
  T8: "语言",
};

const TRAIT_ORDER = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"] as const;

export function formatTraitLevelsCompact(traitLevels: Record<string, string | undefined> | null): string {
  if (!traitLevels) return "—";
  const parts = TRAIT_ORDER.map((tid) => {
    const lv = traitLevels[tid];
    if (!lv) return null;
    const name = TRAIT_SHORT[tid] ?? tid;
    const levelText = LEVEL_LABELS[lv]?.replace(/^L\d+\s*/, "") ?? lv;
    return `${name} ${lv}（${levelText}）`;
  }).filter((x): x is string => Boolean(x));
  return parts.length ? parts.join(" · ") : "—";
}
