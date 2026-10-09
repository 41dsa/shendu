/** 与后端 normalize_llm_report_payload 对齐，用于旧报告兜底展示 */

type Raw = Record<string, unknown>;

function toNum(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function parseScoreValue(v: unknown): number | null {
  if (v == null) return null;
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const m = v.replace(/\s/g, "").match(/([\d]+(?:\.\d+)?)/);
    if (m) return Number(m[1]);
  }
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function payloadSection(p: Raw, ...names: string[]): unknown {
  for (const name of names) {
    if (name in p) return p[name];
  }
  for (const key of Object.keys(p)) {
    for (const name of names) {
      if (key === name || key.endsWith(`_${name}`) || key.includes(name)) return p[key];
    }
  }
  return undefined;
}

function dimensionRows(section: unknown): Raw[] {
  if (Array.isArray(section)) {
    return section.filter((r): r is Raw => !!r && typeof r === "object");
  }
  if (section && typeof section === "object") {
    const o = section as Raw;
    for (const key of ["维度", "dimensions", "items", "分项", "scoring_points"]) {
      const block = o[key];
      if (Array.isArray(block)) {
        return block.filter((r): r is Raw => !!r && typeof r === "object");
      }
    }
  }
  return [];
}

function issueRows(p: Raw): Raw[] {
  const core = payloadSection(p, "核心问题", "problems", "issues");
  if (Array.isArray(core)) {
    return core.filter((r): r is Raw => !!r && typeof r === "object");
  }
  return [];
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

  const summary = payloadSection(p, "综合评分") as Raw | undefined;
  if (p.total_score == null && summary && summary.总分 != null) {
    const parsed = parseScoreValue(summary.总分);
    if (parsed != null) p.total_score = parsed;
  }

  if (!Array.isArray(p.scoring_points) || p.scoring_points.length === 0) {
    const section = payloadSection(p, "分项评分", "dimensions");
    const rows = dimensionRows(section);
    const points: Raw[] = [];
    rows.forEach((r, i) => {
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
    p.scoring_points = points;
  }

  if (!Array.isArray(p.issues) || p.issues.length === 0) {
    const issues: Raw[] = [];
    issueRows(p)
      .slice(0, 5)
      .forEach((r) => {
        const problem = String(r.问题 ?? r.explanation ?? "").trim();
        const why = String(r.为什么扣分 ?? "").trim();
        let explanation = String(r.explanation ?? problem).trim();
        if (why && !explanation.includes(why)) {
          explanation = explanation ? `${explanation} ${why}` : why;
        }
        issues.push({
          tag: String(r.tag ?? "").trim() || problem,
          severity: r.severity ?? "moderate",
          explanation,
          user_quote: r.user_quote ?? r.原文表现 ?? "",
        });
      });
    p.issues = issues;
  }

  if (!Array.isArray(p.suggestions) || p.suggestions.length === 0) {
    const suggestions: string[] = [];
    const prio = payloadSection(p, "修改优先级") as Raw | undefined;
    if (prio) {
      for (const [key, block] of Object.entries(prio)) {
        if (
          Array.isArray(block) &&
          (key.includes("改") || key.includes("建议") || key === "items" || key === "优先修改")
        ) {
          suggestions.push(...block.map(String));
        }
      }
    }
    issueRows(p).forEach((r) => {
      const fix = r.如何改 ?? r.修改建议 ?? r.修改方向;
      if (fix) suggestions.push(String(fix));
    });
    p.suggestions = suggestions.slice(0, 8);
  }

  return p;
}
