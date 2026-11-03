/** 主动学习池：管理端中文展示（不暴露英文 reason / JSON 字段名） */

import { TRAIT_LABELS as TRAIT_NAME, formatQuestionLabel } from "./traitLabels";

const REASON_ZH: Record<string, { label: string; hint: string }> = {
  trait_vote_spread: {
    label: "模型分歧大",
    hint: "多模型对 Trait 等级不一致，整体投票 spread 超阈值",
  },
  evidence_insufficient: {
    label: "证据不足",
    hint: "多个维度缺少可展示的正向证据",
  },
  standard_match_low: {
    label: "标准匹配偏低",
    hint: "题目与标准卡匹配置信度较低",
  },
  level_boundary: {
    label: "等级边界",
    hint: "多个维度落在中间档且置信偏低，边界样本",
  },
  user_dispute: {
    label: "用户申诉",
    hint: "用户对批改结果提交争议",
  },
  self_consistency: {
    label: "单维分歧",
    hint: "至少一个 Trait 维度上模型投票 spread 偏大",
  },
};

const SCORE_MODE_ZH: Record<string, string> = {
  tier_only: "仅展示能力档位",
  interval: "展示分数区间",
  center: "展示区间中心分",
};


export function activeLearningReasonLabel(reason: string): string {
  return REASON_ZH[reason]?.label ?? "待复核难例";
}

export function activeLearningReasonHint(reason: string): string {
  return REASON_ZH[reason]?.hint ?? "";
}

export function activeLearningReasonColor(reason: string): string {
  const map: Record<string, string> = {
    trait_vote_spread: "orange",
    evidence_insufficient: "red",
    standard_match_low: "blue",
    level_boundary: "purple",
    user_dispute: "magenta",
    self_consistency: "gold",
  };
  return map[reason] ?? "default";
}

export function formatActiveLearningQuestionId(qid: string | null | undefined): string {
  return formatQuestionLabel(qid);
}

function fmtNum(v: unknown, digits = 2): string {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
}

function traitLine(row: Record<string, unknown>): string | null {
  const tid = String(row.trait_id ?? "").trim();
  if (!tid) return null;
  const name = TRAIT_NAME[tid] ?? tid;
  const lv = row.level != null ? String(row.level) : "—";
  const parts = [`${name} ${lv}`];
  if (row.vote_spread != null) {
    parts.push(`投票分歧 ${fmtNum(row.vote_spread)}`);
  }
  if (row.evidence_insufficient) {
    parts.push("证据不足");
  }
  return parts.join("；");
}

/** 入池快照 → 多行中文摘要 */
export function formatActiveLearningSnapshot(snapshot: Record<string, unknown> | null): string[] {
  if (!snapshot || typeof snapshot !== "object") return ["—"];

  if (snapshot.dispute_reason != null || snapshot.report_id != null) {
    const lines: string[] = ["来源：用户申诉"];
    if (snapshot.report_id) {
      lines.push(`报告编号：${String(snapshot.report_id).slice(0, 8)}…`);
    }
    const reason = String(snapshot.dispute_reason ?? "").trim();
    if (reason) lines.push(`申诉说明：${reason.slice(0, 80)}${reason.length > 80 ? "…" : ""}`);
    return lines;
  }

  if (snapshot.retry_trait_delta || snapshot.major_changes != null) {
    const lines: string[] = ["来源：重作前后 Trait 变化"];
    const major = snapshot.major_changes;
    if (major != null) lines.push(`主要变动维度数：${String(major)}`);
    const deltas = snapshot.retry_trait_delta;
    if (Array.isArray(deltas)) {
      for (const d of deltas.slice(0, 4)) {
        if (!d || typeof d !== "object") continue;
        const row = d as Record<string, unknown>;
        const tid = String(row.trait_id ?? "");
        const name = TRAIT_NAME[tid] ?? tid;
        lines.push(
          `${name}：${String(row.prior_level ?? "?")} → ${String(row.current_level ?? "?")}`,
        );
      }
    }
    return lines.length > 1 ? lines : ["来源：重作 Trait 波动"];
  }

  const lines: string[] = [];
  if (snapshot.trait_vote_max_spread != null) {
    lines.push(`Trait 投票最大分歧：${fmtNum(snapshot.trait_vote_max_spread)}`);
  }
  if (snapshot.trait_confidence != null) {
    lines.push(`诊断置信度：${fmtNum(snapshot.trait_confidence)}`);
  }
  if (snapshot.ability_level != null && String(snapshot.ability_level).trim()) {
    lines.push(`综合能力：${String(snapshot.ability_level)}`);
  }
  const mode = snapshot.score_display_mode != null ? String(snapshot.score_display_mode) : "";
  if (mode) {
    lines.push(`出分展示：${SCORE_MODE_ZH[mode] ?? mode}`);
  }

  const traits = snapshot.traits;
  if (Array.isArray(traits) && traits.length > 0) {
    const hot = traits
      .filter((t) => t && typeof t === "object")
      .map((t) => traitLine(t as Record<string, unknown>))
      .filter((x): x is string => Boolean(x))
      .filter((line) => line.includes("投票分歧") || line.includes("证据不足"))
      .slice(0, 3);
    if (hot.length > 0) {
      lines.push("重点关注维度：");
      lines.push(...hot.map((h) => `· ${h}`));
    }
  }

  return lines.length > 0 ? lines : ["—"];
}

export function formatActiveLearningTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { hour12: false });
}
