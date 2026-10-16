type ScoringPointRow = {
  id?: string;
  label?: string;
  ability?: string;
};

export type PointHitRow = {
  point_id?: string;
  dimension_id?: string;
  label?: string;
  point_text?: string;
  status?: string;
  earned?: number;
  max_score?: number;
  reason?: string;
  suggestion?: string;
};

const STATUS_LABEL: Record<string, string> = {
  hit: "命中",
  partial: "部分",
  borderline: "部分",
  missed: "未中",
  miss: "未中",
  advisory: "参考",
};

const STATUS_COLOR: Record<string, string> = {
  hit: "success",
  partial: "warning",
  borderline: "warning",
  missed: "default",
  miss: "default",
  advisory: "processing",
};

const DIM_HINTS: Record<string, string[]> = {
  D01: ["立意", "题意", "观点"],
  D02: ["结构", "逻辑", "层次"],
  D03: ["论证", "材料", "内容", "论据"],
  D04: ["语言", "表达"],
};

function dimensionHints(row: ScoringPointRow): string[] {
  const id = String(row.id ?? "").trim();
  const fromId = DIM_HINTS[id] ?? [];
  const label = String(row.label ?? "");
  const fromLabel: string[] = [];
  for (const hints of Object.values(DIM_HINTS)) {
    for (const h of hints) {
      if (label.includes(h)) fromLabel.push(h);
    }
  }
  return [...new Set([...fromId, ...fromLabel])];
}

function hitBelongsToDimension(hit: PointHitRow, row: ScoringPointRow): boolean {
  const dimId = String(row.id ?? "").trim();
  const hDim = String(hit.dimension_id ?? "").trim();
  if (hDim && dimId) return dimId === hDim;
  if (hDim) return false;
  if (dimId && String(hit.point_id ?? "") === dimId) return true;

  const hints = dimensionHints(row);
  if (!hints.length) return false;
  const blob = `${hit.point_text ?? ""} ${hit.label ?? ""}`;
  return hints.some((h) => blob.includes(h));
}

export function parsePointHitsFromPayload(payload: Record<string, unknown>): PointHitRow[] {
  const eng = payload.scoring_engine;
  if (!eng || typeof eng !== "object") return [];
  const hits = (eng as Record<string, unknown>).point_hits;
  if (!Array.isArray(hits)) return [];
  return hits.filter((h): h is PointHitRow => h != null && typeof h === "object") as PointHitRow[];
}

function dedupeHits(matched: PointHitRow[]): PointHitRow[] {
  const seen = new Set<string>();
  const out: PointHitRow[] = [];
  for (const h of matched) {
    const key = String(h.point_id ?? h.label ?? "");
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    out.push(h);
  }
  return out;
}

export function criteriaHitsForDimension(
  dimensionRow: ScoringPointRow,
  allHits: PointHitRow[],
): PointHitRow[] {
  if (!allHits.length) return [];
  return dedupeHits(allHits.filter((h) => hitBelongsToDimension(h, dimensionRow))).slice(0, 10);
}

/** 展示用：优先有分的细项；纯未中条目合并为计数，避免误以为「维度 0 分」 */
export function criteriaHitsForDisplay(
  dimensionRow: ScoringPointRow,
  allHits: PointHitRow[],
): { scored: PointHitRow[]; missedCount: number } {
  const matched = dedupeHits(allHits.filter((h) => hitBelongsToDimension(h, dimensionRow)));
  const scored = matched.filter((h) => {
    const er = Number(h.earned);
    if (Number.isFinite(er) && er > 0) return true;
    const st = String(h.status ?? "");
    return st === "borderline" || st === "partial" || st === "advisory";
  });
  const missedCount = matched.filter((h) => {
    const er = Number(h.earned);
    const st = String(h.status ?? "");
    return (!Number.isFinite(er) || er <= 0) && (st === "missed" || st === "miss");
  }).length;
  return { scored: scored.slice(0, 8), missedCount };
}

export function statusLabel(status: string | undefined): string {
  return STATUS_LABEL[status ?? ""] ?? status ?? "—";
}

export function statusTagColor(status: string | undefined): string {
  return STATUS_COLOR[status ?? ""] ?? "default";
}

export function criteriaHitTitle(hit: PointHitRow): string {
  const text = String(hit.point_text ?? hit.label ?? hit.point_id ?? "采分点").trim();
  return text.length > 56 ? `${text.slice(0, 53)}…` : text;
}

export function criteriaScoreLine(hit: PointHitRow): string | null {
  const mx = Number(hit.max_score);
  const er = Number(hit.earned);
  if (!Number.isFinite(mx) || mx <= 0) return null;
  const earned = Number.isFinite(er) ? Math.min(er, mx) : 0;
  return `${earned}/${mx} 分`;
}
