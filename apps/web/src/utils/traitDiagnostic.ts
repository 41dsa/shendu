/** PRD V1：八大 Trait 诊断与报告头 7 问 */

type Raw = Record<string, unknown>;

export type TraitEvidenceSpan = {
  quote: string;
  para?: number | null;
  start?: number | null;
  end?: number | null;
  grounded?: boolean;
};

export type TraitDiagnosticRow = {
  trait_id: string;
  name: string;
  standard_tier?: string;
  level?: string;
  participates_in_score?: boolean;
  confidence?: number;
  evidence_positive: string[];
  evidence_negative: string[];
  evidence_missing: string[];
  evidence_spans?: TraitEvidenceSpan[];
  conclusion?: string;
  dispute_hint?: string;
  model_votes?: { level?: string; model?: string }[];
  evidence_insufficient?: boolean;
};

export type DiagnosticSevenQuestions = {
  q1_task: string;
  q2_met: string[];
  q3_evidence: string[];
  q4_unmet: string[];
  q5_loss: string[];
  q6_disputes: string[];
  q7_next: string[];
};

const LEVEL_COLOR: Record<string, string> = {
  L4: "green",
  L3: "cyan",
  L2: "blue",
  L1: "orange",
  L0: "red",
};

export function traitLevelColor(level: string | undefined): string {
  return LEVEL_COLOR[String(level ?? "").toUpperCase()] ?? "default";
}

export function isTraitV1Report(p: Raw): boolean {
  const eng = p.scoring_engine as Raw | undefined;
  if (Array.isArray(p.trait_diagnostics) && p.trait_diagnostics.length > 0) return true;
  if (eng && (eng.engine === "diagnostic_trait_v1" || Array.isArray(eng.trait_diagnostics))) return true;
  return false;
}

function normalizeTraitRow(row: unknown): TraitDiagnosticRow | null {
  if (!row || typeof row !== "object") return null;
  const r = row as Raw;
  const tid = String(r.trait_id ?? "").trim();
  if (!tid) return null;
  return {
    trait_id: tid,
    name: String(r.name ?? tid),
    standard_tier: r.standard_tier != null ? String(r.standard_tier) : undefined,
    level: r.level != null ? String(r.level) : undefined,
    participates_in_score: r.participates_in_score as boolean | undefined,
    confidence: r.confidence != null ? Number(r.confidence) : undefined,
    evidence_positive: strList(r.evidence_positive),
    evidence_negative: strList(r.evidence_negative),
    evidence_missing: strList(r.evidence_missing),
    evidence_spans: Array.isArray(r.evidence_spans)
      ? (r.evidence_spans as Raw[]).map((sp) => ({
          quote: String(sp.quote ?? ""),
          para: sp.para != null ? Number(sp.para) : null,
          start: sp.start != null ? Number(sp.start) : null,
          end: sp.end != null ? Number(sp.end) : null,
          grounded: sp.grounded !== false,
        }))
      : undefined,
    conclusion: r.conclusion != null ? String(r.conclusion) : undefined,
    dispute_hint: r.dispute_hint != null ? String(r.dispute_hint) : undefined,
    model_votes: Array.isArray(r.model_votes)
      ? (r.model_votes as Raw[]).map((v) => ({
          level: v.level != null ? String(v.level) : undefined,
          model: v.model != null ? String(v.model) : undefined,
        }))
      : undefined,
    evidence_insufficient: Boolean(r.evidence_insufficient),
  };
}

const TRAIT_ORDER = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"];

function listUnique(items: string[]): string[] {
  return [...new Set(items.map((x) => x.trim()).filter(Boolean))];
}

function strList(v: unknown): string[] {
  return Array.isArray(v) ? v.map((x) => String(x).trim()).filter(Boolean) : [];
}

export function parseTraitDiagnostics(p: Raw): TraitDiagnosticRow[] {
  const eng = p.scoring_engine as Raw | undefined;
  const raw =
    (Array.isArray(p.trait_diagnostics) ? p.trait_diagnostics : null) ??
    (eng && Array.isArray(eng.trait_diagnostics) ? eng.trait_diagnostics : null) ??
    [];
  const rows = raw.map(normalizeTraitRow).filter((x): x is TraitDiagnosticRow => x != null);
  rows.sort((a, b) => TRAIT_ORDER.indexOf(a.trait_id) - TRAIT_ORDER.indexOf(b.trait_id));
  return rows;
}

export function parseDiagnosticHeader(
  p: Raw,
  opts: { prompt?: string; suggestions?: string[] },
): DiagnosticSevenQuestions {
  const eng = p.scoring_engine as Raw | undefined;
  const header = (p.diagnostic_header ?? eng?.diagnostic_header) as Raw | undefined;

  const traits = parseTraitDiagnostics(p);
  const allPos = traits.flatMap((t) => t.evidence_positive);
  const allMiss = traits.flatMap((t) => t.evidence_missing);
  const stdDisputes = strList(p.standard_dispute_marks);
  const disputes = listUnique(
    stdDisputes.concat(
      strList(p.trait_dispute_notes) ||
        strList(eng?.trait_dispute_notes) ||
        traits.map((t) => t.dispute_hint ?? "").filter(Boolean),
    ),
  );
  const loss =
    strList(p.primary_loss_traits) ||
    strList(eng?.primary_loss_traits) ||
    strList(header?.q5_loss_sources);

  return {
    q1_task: String(header?.q1_task ?? opts.prompt ?? "").trim(),
    q2_met: strList(header?.q2_met).length
      ? strList(header?.q2_met)
      : traits
          .filter((t) => t.level && (t.level === "L3" || t.level === "L4"))
          .map((t) => `${t.name}（${t.level}）`),
    q3_evidence: allPos.slice(0, 8),
    q4_unmet: allMiss.slice(0, 8),
    q5_loss: loss,
    q6_disputes: disputes.slice(0, 6),
    q7_next: strList(header?.q7_next_steps).length
      ? strList(header?.q7_next_steps)
      : (opts.suggestions ?? []).slice(0, 5),
  };
}

export function resolveAbilityLevel(p: Raw): string | null {
  const eng = p.scoring_engine as Raw | undefined;
  const v = p.ability_level ?? eng?.ability_level;
  return v != null && String(v).trim() ? String(v) : null;
}

export function resolveScoreDisclaimer(p: Raw): string | null {
  const eng = p.scoring_engine as Raw | undefined;
  const d = p.score_disclaimer ?? eng?.score_disclaimer;
  return d != null && String(d).trim() ? String(d) : null;
}

export function resolveTraitConfidence(p: Raw): number | null {
  const eng = p.scoring_engine as Raw | undefined;
  const v = p.trait_confidence ?? eng?.trait_confidence;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export type ScoreDisplayMode = "tier_only" | "interval" | "center";

export function resolveScoreDisplayMode(p: Raw): ScoreDisplayMode | null {
  const eng = p.scoring_engine as Raw | undefined;
  const raw = p.score_display_mode ?? eng?.score_display_mode;
  const s = String(raw ?? "").trim();
  if (s === "tier_only" || s === "interval" || s === "center") return s;
  return null;
}

export function resolveHumanReviewRecommended(p: Raw): boolean {
  return Boolean(p.human_review_recommended ?? (p.scoring_engine as Raw | undefined)?.human_review_recommended);
}

export function resolveHumanReviewNote(p: Raw): string | null {
  const note = p.human_review_note ?? (p.scoring_engine as Raw | undefined)?.human_review_note;
  return note != null && String(note).trim() ? String(note) : null;
}

export function resolveStandardDisputeMarks(p: Raw): string[] {
  return listUnique(strList(p.standard_dispute_marks));
}

export type MultiStandardViews = {
  labels?: {
    strict?: string;
    loose?: string;
    baseline?: string;
    dependency?: string;
  };
  strict?: { score_min?: number; score_max?: number; system_center?: number; ability_level?: string };
  loose?: { score_min?: number; score_max?: number; system_center?: number; ability_level?: string };
  baseline?: { score_min?: number; score_max?: number; system_center?: number; ability_level?: string };
  dependency?: {
    label?: string;
    traits?: { trait_id: string; name: string; level?: string; dispute_hint?: string; conclusion?: string }[];
    dispute_notes?: string[];
  };
};

export type AnchorRelativeScale = {
  anchor_count?: number;
  nearest_anchor_id?: string;
  nearest_anchor_title?: string;
  distance?: number;
  trait_gaps?: { trait_id: string; essay_level?: string; anchor_level?: string; delta?: number }[];
};

export function resolveAnchorRelativeScale(p: Raw): AnchorRelativeScale | null {
  const eng = p.scoring_engine as Raw | undefined;
  const raw =
    p.anchor_relative_scale ??
    eng?.anchor_relative_scale ??
    (p.diagnostic_header as Raw | undefined)?.anchor_relative_scale;
  return raw && typeof raw === "object" ? (raw as AnchorRelativeScale) : null;
}

export function resolveAnchorCount(p: Raw): number | null {
  const eng = p.scoring_engine as Raw | undefined;
  const v = p.anchor_count ?? eng?.anchor_count;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function resolveMultiStandardViews(p: Raw): MultiStandardViews | null {
  const eng = p.scoring_engine as Raw | undefined;
  const raw = p.multi_standard_views ?? eng?.multi_standard_views;
  return raw && typeof raw === "object" ? (raw as MultiStandardViews) : null;
}
