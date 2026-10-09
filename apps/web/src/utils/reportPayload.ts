/** 与后端 normalize_llm_report_payload 对齐，用于旧报告兜底展示 */

type Raw = Record<string, unknown>;

function toNum(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function inferHit(earned: number, max: number): string {
  if (max <= 0) return "miss";
  const r = earned / max;
  if (r >= 0.85) return "full";
  if (r >= 0.5) return "partial";
  return "miss";
}

export function normalizeReportPayload(raw: Raw): Raw {
  const p = { ...raw };
  if (Array.isArray(p.scoring_points) && p.scoring_points.length > 0 && Array.isArray(p.issues)) {
    return p;
  }

  if (p.total_score == null) {
    const summary = p.综合评分 as Raw | undefined;
    if (summary && summary.总分 != null) p.total_score = toNum(summary.总分);
  }

  if (!Array.isArray(p.scoring_points) || p.scoring_points.length === 0) {
    const rows = (p.分项评分 ?? p.dimensions) as unknown[];
    const points: Raw[] = [];
    if (Array.isArray(rows)) {
      rows.forEach((row, i) => {
        if (!row || typeof row !== "object") return;
        const r = row as Raw;
        const earned = toNum(r.earned ?? r.得分 ?? r.score);
        const max = toNum(r.max ?? r.满分 ?? r.max_score, 10);
        points.push({
          id: r.id ?? `D${String(i + 1).padStart(2, "0")}`,
          label: r.label ?? r.评分维度 ?? r.name ?? `维度${i + 1}`,
          earned,
          max,
          hit: r.hit ?? inferHit(earned, max),
          reason: r.reason ?? r.主要原因 ?? r.说明 ?? "",
        });
      });
    }
    p.scoring_points = points;
  }

  if (!Array.isArray(p.issues) || p.issues.length === 0) {
    const core = p.核心问题 as unknown[];
    const issues: Raw[] = [];
    if (Array.isArray(core)) {
      core.slice(0, 5).forEach((row, i) => {
        if (!row || typeof row !== "object") return;
        const r = row as Raw;
        issues.push({
          tag: r.tag ?? `问题${i + 1}`,
          severity: r.severity ?? "moderate",
          explanation: r.explanation ?? r.问题 ?? "",
          user_quote: r.user_quote ?? r.原文表现 ?? "",
        });
      });
    }
    p.issues = issues;
  }

  if (!Array.isArray(p.suggestions) || p.suggestions.length === 0) {
    const suggestions: string[] = [];
    const prio = p.修改优先级 as Raw | undefined;
    if (prio && Array.isArray(prio.如果只能改3个地方)) {
      suggestions.push(...prio.如果只能改3个地方.map(String));
    }
    const core = p.核心问题 as Raw[] | undefined;
    core?.forEach((r) => {
      if (r?.如何改) suggestions.push(String(r.如何改));
    });
    p.suggestions = suggestions.slice(0, 8);
  }

  return p;
}
