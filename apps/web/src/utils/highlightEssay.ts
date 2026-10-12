export type KeepSegment = { quote: string; reason?: string };

export type HighlightRange = { start: number; end: number; reason?: string; segmentIndex?: number };

export type TextSpan = { start: number; end: number; reason?: string };

export function spansToRanges(content: string, spans: TextSpan[] | undefined): HighlightRange[] {
  if (!content || !spans?.length) return [];
  const ranges: HighlightRange[] = [];
  for (const s of spans) {
    const start = Math.max(0, Math.floor(s.start));
    const end = Math.min(content.length, Math.floor(s.end));
    if (end <= start) continue;
    ranges.push({ start, end, reason: s.reason });
  }
  ranges.sort((a, b) => a.start - b.start);
  return ranges;
}

/** 按 segments 顺序为每条 quote 定位，并带上 1-based 序号（不合并重叠，便于与说明列表对照） */
export function segmentRangesWithIndex(content: string, segments: KeepSegment[]): HighlightRange[] {
  const ranges: HighlightRange[] = [];
  const seen = new Set<string>();
  segments.forEach((seg, idx) => {
    const quote = (seg.quote || "").trim();
    if (quote.length < 4) return;
    const start = content.indexOf(quote);
    if (start < 0) return;
    const end = start + quote.length;
    const key = `${start}:${end}`;
    if (seen.has(key)) return;
    seen.add(key);
    ranges.push({ start, end, reason: seg.reason, segmentIndex: idx + 1 });
  });
  ranges.sort((a, b) => a.start - b.start);
  return ranges;
}

export function findKeepRanges(content: string, segments: KeepSegment[]): HighlightRange[] {
  const ranges: HighlightRange[] = [];
  const seen = new Set<string>();
  for (const seg of segments) {
    const quote = (seg.quote || "").trim();
    if (quote.length < 4) continue;
    const start = content.indexOf(quote);
    if (start < 0) continue;
    const end = start + quote.length;
    const key = `${start}:${end}`;
    if (seen.has(key)) continue;
    seen.add(key);
    ranges.push({ start, end, reason: seg.reason });
  }
  ranges.sort((a, b) => a.start - b.start);
  const merged: HighlightRange[] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r.start <= last.end) {
      last.end = Math.max(last.end, r.end);
      if (r.reason && !last.reason) last.reason = r.reason;
    } else {
      merged.push({ ...r });
    }
  }
  return merged;
}

export type HighlightPiece = { text: string; highlight: boolean; reason?: string; segmentIndex?: number };

export function highlightCoverageRatio(content: string, ranges: HighlightRange[]): number {
  if (!content.length || !ranges.length) return 0;
  let covered = 0;
  for (const r of ranges) {
    covered += Math.max(0, r.end - r.start);
  }
  return covered / content.length;
}

function mergeHighlightRanges(ranges: HighlightRange[]): HighlightRange[] {
  if (!ranges.length) return [];
  const sorted = [...ranges].sort((a, b) => a.start - b.start);
  const merged: HighlightRange[] = [{ ...sorted[0] }];
  for (const r of sorted.slice(1)) {
    const last = merged[merged.length - 1];
    if (r.start <= last.end) {
      last.end = Math.max(last.end, r.end);
    } else {
      merged.push({ ...r });
    }
  }
  return merged;
}

/** 高亮过多时优先保留较短片段，而不是整篇取消标色 */
export function trimRangesToMaxCoverage(
  content: string,
  ranges: HighlightRange[],
  maxCoverage = 0.32,
): HighlightRange[] {
  if (!ranges.length) return [];
  const byLen = [...ranges].sort((a, b) => a.end - a.start - (b.end - b.start));
  const kept: HighlightRange[] = [];
  for (const r of byLen) {
    kept.push(r);
    if (highlightCoverageRatio(content, mergeHighlightRanges(kept)) > maxCoverage) {
      kept.pop();
    }
  }
  return mergeHighlightRanges(kept);
}

export function splitForHighlight(content: string, ranges: HighlightRange[]): HighlightPiece[] {
  if (!content) return [];
  if (ranges.length === 0) return [{ text: content, highlight: false }];
  const pieces: HighlightPiece[] = [];
  let cursor = 0;
  for (const r of ranges) {
    if (r.start > cursor) {
      pieces.push({ text: content.slice(cursor, r.start), highlight: false });
    }
    if (r.end > r.start) {
      pieces.push({
        text: content.slice(r.start, r.end),
        highlight: true,
        reason: r.reason,
        segmentIndex: r.segmentIndex,
      });
    }
    cursor = Math.max(cursor, r.end);
  }
  if (cursor < content.length) {
    pieces.push({ text: content.slice(cursor), highlight: false });
  }
  return pieces;
}
