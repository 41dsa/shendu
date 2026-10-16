import { normalizeSuggestionsList } from "./suggestionDisplay";

/** 与后端 normalize_llm_report_payload 对齐，用于旧报告兜底展示 */

type Raw = Record<string, unknown>;

function toNum(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

export function parseScoreValue(v: unknown): number | null {
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

/** 维度卡片「命中/未命中」与 earned/max 一致（忽略 stale 的 LLM hit）。 */
export function resolveScoringPointHit(
  earned: unknown,
  max: unknown,
  _legacyHit?: unknown,
): string {
  return inferHit(toNum(earned, 0), toNum(max, 10));
}

function syncScoringPointsHit(p: Raw): void {
  const pts = p.scoring_points;
  if (!Array.isArray(pts)) return;
  for (const row of pts) {
    if (!row || typeof row !== "object") continue;
    const pt = row as Raw;
    pt.hit = resolveScoringPointHit(pt.earned, pt.max, pt.hit);
  }
}

const HOLISTIC_LABELS = new Set(["总分", "综合评分", "综合得分", "卷面总分", "总分得分"]);

function isHolisticDimensionRow(label: string, max: number, essayMax: number): boolean {
  const lab = label.trim();
  if (!lab) return false;
  if (HOLISTIC_LABELS.has(lab)) return true;
  if (lab.startsWith("总分") && max >= essayMax * 0.85) return true;
  return false;
}

function stripHolisticDimensionRows(p: Raw): void {
  const pts = p.scoring_points;
  if (!Array.isArray(pts) || pts.length === 0) return;
  const essayMax = toNum(p.max_score, 40);
  const kept: Raw[] = [];
  let stripped = 0;
  for (const row of pts) {
    if (!row || typeof row !== "object") {
      kept.push(row as Raw);
      continue;
    }
    const label = String(row.label ?? "");
    const mx = toNum(row.max, 0);
    if (isHolisticDimensionRow(label, mx, essayMax)) {
      stripped += 1;
      const reason = String(row.reason ?? "").trim();
      if (reason) {
        const existing = p.review_notes != null ? String(p.review_notes).trim() : "";
        if (!existing) p.review_notes = reason;
        else if (!existing.includes(reason)) p.review_notes = `${existing} ${reason}`.trim();
      }
      continue;
    }
    kept.push(row as Raw);
  }
  if (stripped > 0) p.scoring_points = kept;
}

export function normalizeReportPayload(raw: Raw): Raw {
  const p = { ...raw };

  const summary = payloadSection(p, "综合评分") as Raw | undefined;
  if (summary && summary.总分 != null) {
    const parsed = parseScoreValue(summary.总分);
    const current = p.total_score == null ? null : Number(p.total_score);
    if (
      parsed != null &&
      (current == null || !Number.isFinite(current) || (current <= 0 && parsed > 0))
    ) {
      p.total_score = parsed;
    }
  }

  if (!Array.isArray(p.scoring_points) || p.scoring_points.length === 0) {
    const section = payloadSection(p, "分项评分", "dimensions");
    const rows = dimensionRows(section);
    const points: Raw[] = [];
    const essayMax = toNum(p.max_score, 40);
    rows.forEach((r, i) => {
      const earned = toNum(r.earned ?? r.得分 ?? r.score);
      const max = toNum(r.max ?? r.满分 ?? r.max_score, 10);
      const label = String(r.label ?? r.评分维度 ?? r.name ?? `维度${i + 1}`);
      if (isHolisticDimensionRow(label, max, essayMax) && rows.length > 1) return;
      points.push({
        id: r.id ?? `D${String(i + 1).padStart(2, "0")}`,
        label,
        earned,
        max,
        hit: inferHit(earned, max),
        reason: r.reason ?? r.主要原因 ?? r.说明 ?? "",
      });
    });
    p.scoring_points = points;
  }

  stripHolisticDimensionRows(p);
  syncScoringPointsHit(p);

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

  const summaryReviewKeys = ["总体说明", "总体得分原因", "总体原因", "总体评价", "总体评述"] as const;
  if (summary && typeof summary === "object") {
    const s = summary as Raw;
    let excerpt = "";
    for (const key of summaryReviewKeys) {
      const val = s[key];
      if (val != null && String(val).trim()) {
        excerpt = String(val).trim();
        break;
      }
    }
    const existing = p.review_notes != null ? String(p.review_notes).trim() : "";
    const tierLike = /^[一二三四]类文[（(]/.test(existing);
    const gradeReq = String(p.grade_by_requirements ?? "").trim();
    const fullTier = String(p.grade_tier_full_by_requirements ?? "").trim();
    const totalScore = parseScoreValue(p.total_score);

    const tierHead = (s: string) => s.match(/^([一二三四]类)文/)?.[1] ?? "";
    const tierConflict =
      Boolean(gradeReq && excerpt && tierHead(excerpt) && tierHead(`${gradeReq}文`)) &&
      tierHead(excerpt) !== tierHead(`${gradeReq}文`);

    const canonicalReviewFromGrade = (): string => {
      if (fullTier && totalScore != null) return `${fullTier}，约${totalScore}分`;
      if (gradeReq && totalScore != null) return `${gradeReq}，约${totalScore}分`;
      return fullTier || gradeReq;
    };

    if (excerpt && (!existing || tierLike)) {
      if (tierConflict || (tierLike && gradeReq)) {
        const canonical = canonicalReviewFromGrade();
        if (canonical) p.review_notes = canonical;
        else if (!tierConflict) p.review_notes = excerpt;
      } else {
        p.review_notes = excerpt;
      }
    } else if (tierLike && !excerpt) {
      const canonical = canonicalReviewFromGrade();
      p.review_notes = canonical || "";
    }
  }

  const ENGINE_DIM_REASON = "确定性引擎按采分点覆盖率聚合";
  const sectionScores = payloadSection(p, "分项评分", "dimensions");
  const rubricRows = dimensionRows(sectionScores);
  if (rubricRows.length > 0 && Array.isArray(p.scoring_points)) {
    const byLabel = new Map<string, string>();
    for (const row of rubricRows) {
      const label = String(row.label ?? row.评分维度 ?? row.name ?? "").trim();
      const reason = String(row.reason ?? row.主要原因 ?? row.说明 ?? "").trim();
      if (label && reason && reason !== ENGINE_DIM_REASON) {
        byLabel.set(label, reason);
      }
    }
    p.scoring_points = (p.scoring_points as Raw[]).map((pt) => {
      if (!pt || typeof pt !== "object") return pt;
      const lab = String(pt.label ?? "").trim();
      const cur = String(pt.reason ?? "").trim();
      if (lab && byLabel.has(lab) && (!cur || cur === ENGINE_DIM_REASON)) {
        return { ...pt, reason: byLabel.get(lab) };
      }
      return pt;
    });
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

  hydrateAltLlmSchema(p);

  if (Array.isArray(p.suggestions)) {
    p.suggestions = normalizeSuggestionsList(p.suggestions);
  }

  syncScoringPointsHit(p);
  return p;
}

function issuesArePlaceholder(issues: unknown): boolean {
  if (!Array.isArray(issues) || issues.length === 0) return true;
  return issues.every((item) => {
    if (!item || typeof item !== "object") return true;
    const exp = String((item as Raw).explanation ?? "").trim();
    const tag = String((item as Raw).tag ?? "").trim();
    return (!exp || exp.length < 8) && (tag === "作答问题" || !tag);
  });
}

function scoringPointsEngineOnly(points: unknown): boolean {
  if (!Array.isArray(points) || points.length === 0) return true;
  const ENGINE = "确定性引擎按采分点覆盖率聚合";
  return (points as Raw[]).every((pt) => {
    if (!pt || typeof pt !== "object") return true;
    const reason = String(pt.reason ?? "").trim();
    return !reason || reason === ENGINE;
  });
}

/** 与后端 hydrate_report_display_fields 对齐 */
function hydrateAltLlmSchema(p: Raw): void {
  const dimensionScores = p.dimension_scores;
  if (Array.isArray(dimensionScores) && dimensionScores.length > 0) {
    if (scoringPointsEngineOnly(p.scoring_points)) {
      const points: Raw[] = [];
      dimensionScores.forEach((row, i) => {
        if (!row || typeof row !== "object") return;
        const r = row as Raw;
        const earned = toNum(r.earned ?? r.score);
        const max = toNum(r.max ?? r.max_score, 10);
        const label = String(r.dimension ?? r.label ?? `维度${i + 1}`);
        points.push({
          id: r.id ?? `D${String(i + 1).padStart(2, "0")}`,
          label,
          earned,
          max,
          hit: inferHit(earned, max),
          reason: String(r.reason ?? r.说明 ?? ""),
        });
      });
      if (points.length) p.scoring_points = points;
    }
  }
  syncScoringPointsHit(p);

  const coreProblems = p.core_problems;
  if (Array.isArray(coreProblems) && coreProblems.length > 0 && issuesArePlaceholder(p.issues)) {
    const issues: Raw[] = [];
    for (const row of coreProblems.slice(0, 5)) {
      if (!row || typeof row !== "object") continue;
      const r = row as Raw;
      const title = String(r.title ?? "").trim();
      const problem = String(r.problem ?? "").trim();
      const impact = String(r.impact ?? "").trim();
      const revision = String(r.revision ?? "").trim();
      let explanation = problem;
      if (impact) explanation = problem ? `${problem} ${impact}`.trim() : impact;
      if (!explanation && revision) explanation = revision;
      const level = String(r.level ?? "");
      const severity = level.includes("C级") || level.includes("一般") ? "minor" : "moderate";
      issues.push({
        tag: title || "作答问题",
        issue_title: title || undefined,
        severity,
        explanation: explanation || title,
        user_quote: String(r.original ?? "").slice(0, 240),
      });
    }
    if (issues.length) p.issues = issues;
  }

  if (!Array.isArray(p.suggestions) || p.suggestions.length === 0) {
    const suggestions: string[] = [];
    const rp = p.revision_priority;
    if (rp && typeof rp === "object") {
      const block = (rp as Raw).if_only_three_changes ?? (rp as Raw).items;
      if (Array.isArray(block)) {
        for (const x of block) {
          const t = String(x).trim();
          if (t) suggestions.push(t);
        }
      }
    }
    if (!suggestions.length && Array.isArray(coreProblems)) {
      for (const row of coreProblems.slice(0, 5)) {
        if (row && typeof row === "object" && (row as Raw).revision) {
          suggestions.push(String((row as Raw).revision).trim());
        }
      }
    }
    if (suggestions.length) p.suggestions = suggestions.slice(0, 8);
  }

  const existingReview = p.review_notes != null ? String(p.review_notes).trim() : "";
  if (!existingReview) {
    const grade = String(p.grade ?? "").trim();
    const overall = String(p.overall_comment ?? p.overall ?? "").trim();
    if (grade && overall) p.review_notes = `${grade}。${overall}`;
    else if (grade) p.review_notes = grade;
    else if (overall) p.review_notes = overall;
  }
}

function tierClassHead(text: string): string {
  return text.match(/^([一二三四]类)文/)?.[1] ?? "";
}

function replaceTierBandsWithRequirements(text: string, fullTier: string): string {
  if (!fullTier.trim()) return text;
  return text.replace(/[一二三四]类文[（(][^）)]*[）)]/g, fullTier.trim());
}

/** 总评摘要：档次区间与 grade_by_requirements 一致（按作答要求声明的题目满分，非 Rubric 40 分） */
export function resolveReviewNotesDisplay(
  payload: Raw,
  stepsSummary?: string | null,
): string | undefined {
  const gradeReq = String(payload.grade_by_requirements ?? "").trim();
  const fullTier = String(payload.grade_tier_full_by_requirements ?? "").trim();
  const total = parseScoreValue(payload.total_score);
  const canonical =
    fullTier && total != null
      ? `${fullTier}，约${total}分`
      : gradeReq && total != null
        ? `${gradeReq}，约${total}分`
        : fullTier || gradeReq || undefined;

  const raw =
    String(payload.review_notes ?? "").trim() ||
    String(stepsSummary ?? "").trim() ||
    undefined;
  if (!raw) return canonical;
  let display = fullTier ? replaceTierBandsWithRequirements(raw, fullTier) : raw;
  if (!gradeReq) return display;
  const expected = tierClassHead(`${gradeReq}文`);
  const actual = tierClassHead(display);
  if (expected && actual && expected !== actual) return canonical ?? display;
  return display;
}

/** 与后端 display_total_score 对齐 */
/** 总分数置信浮动区间；若与 total 不一致则按置信度本地重算（旧报告兜底）。 */
export function resolveScoreConfidenceRange(
  total: unknown,
  maxScore: number,
  confidence: string,
  rawRange: unknown,
): [number, number] | null {
  const t = parseScoreValue(total);
  if (t == null || t <= 0 || maxScore <= 0) return null;
  const range = Array.isArray(rawRange) ? rawRange.map((x) => Number(x)) : [];
  if (
    range.length === 2 &&
    Number.isFinite(range[0]) &&
    Number.isFinite(range[1]) &&
    range[0] <= t &&
    t <= range[1]
  ) {
    return [range[0], range[1]];
  }
  const conf = String(confidence || "medium").toLowerCase();
  const span = conf === "high" ? 1 : conf === "low" ? 2.5 : 2;
  const round1 = (n: number) => Math.round(n * 10) / 10;
  return [Math.max(0, round1(t - span)), Math.min(maxScore, round1(t + span))];
}

export function displayTotalScore(raw: Raw): number | null {
  const p = normalizeReportPayload({ ...raw });
  return parseScoreValue(p.total_score);
}

export function refreshComparisonScores(
  payload: Raw,
  baselinePayload?: Raw | null,
): Raw {
  const comp = payload.comparison;
  if (!comp || typeof comp !== "object") return payload;
  const comparison = { ...(comp as Raw) };
  const second = displayTotalScore(payload);
  const first =
    baselinePayload != null
      ? displayTotalScore(baselinePayload)
      : parseScoreValue(comparison.first_score);
  if (second != null) comparison.second_score = second;
  if (first != null) comparison.first_score = first;
  if (second != null && first != null) {
    comparison.score_delta = Math.round((second - first) * 10) / 10;
  }
  return { ...payload, comparison };
}
