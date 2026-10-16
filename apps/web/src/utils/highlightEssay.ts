import { locateInEssay } from "./essayLocate";

export type KeepSegment = { quote: string; reason?: string };

export type EditSegmentLike = {
  quote?: string;
  source_quote?: string;
  reason?: string;
};

function rangeForSegmentQuote(content: string, quote: string, reason?: string): HighlightRange | null {
  const q = quote.trim();
  if (q.length < 4) return null;
  const hit = locateInEssay(content, [q], { reason });
  if (hit) return hit;
  return null;
}

export type HighlightRange = {
  start: number;
  end: number;
  reason?: string;
  segmentIndex?: number;
  /** 参考范文：段首分论点句（与采分点橙标区分） */
  variant?: "thesis_lead" | "mark";
};

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
    const hit = rangeForSegmentQuote(content, quote, seg.reason);
    if (!hit) return;
    const key = `${hit.start}:${hit.end}:${idx + 1}`;
    if (seen.has(key)) return;
    seen.add(key);
    ranges.push({ ...hit, reason: seg.reason, segmentIndex: idx + 1 });
  });
  return ranges;
}

function inferSourceQuoteFromLinePair(original: string, rewrite: string, editQuote: string): string {
  const q = editQuote.trim();
  if (q.length < 4 || !rewrite || !original) return "";
  const rPos = rewrite.indexOf(q);
  if (rPos < 0) return "";
  const origLines = original.split("\n");
  const rewLines = rewrite.split("\n");
  if (origLines.length !== rewLines.length) return "";
  let cursor = 0;
  for (let i = 0; i < rewLines.length; i++) {
    const lineEnd = cursor + rewLines[i].length;
    if (rPos >= cursor && rPos < lineEnd + 1) {
      const oLine = origLines[i]?.trim() ?? "";
      const rLine = rewLines[i]?.trim() ?? "";
      if (oLine.length >= 4 && oLine !== rLine) return oLine;
      return "";
    }
    cursor = lineEnd + 1;
  }
  return "";
}

/** 左侧原文：与 edit_segments 同序号的 source_quote 区间 */
export function segmentSourceRangesWithIndex(
  content: string,
  segments: EditSegmentLike[],
  pairedRewrite?: string,
): HighlightRange[] {
  const ranges: HighlightRange[] = [];
  const seen = new Set<string>();
  segments.forEach((seg, idx) => {
    let quote = (seg.source_quote || "").trim();
    if (quote.length < 4 && pairedRewrite && seg.quote) {
      quote = inferSourceQuoteFromLinePair(content, pairedRewrite, seg.quote.trim());
    }
    if (quote.length < 4) return;
    const hit = rangeForSegmentQuote(content, quote, seg.reason);
    if (!hit) return;
    const key = `${hit.start}:${hit.end}:${idx + 1}`;
    if (seen.has(key)) return;
    seen.add(key);
    ranges.push({ ...hit, reason: seg.reason, segmentIndex: idx + 1 });
  });
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

export type HighlightPiece = {
  text: string;
  highlight: boolean;
  reason?: string;
  segmentIndex?: number;
  variant?: "thesis_lead" | "mark";
};

export function highlightCoverageRatio(content: string, ranges: HighlightRange[]): number {
  if (!content.length || !ranges.length) return 0;
  let covered = 0;
  for (const r of ranges) {
    covered += Math.max(0, r.end - r.start);
  }
  return covered / content.length;
}

export function mergeHighlightRanges(ranges: HighlightRange[]): HighlightRange[] {
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
        variant: r.variant,
      });
    }
    cursor = Math.max(cursor, r.end);
  }
  if (cursor < content.length) {
    pieces.push({ text: content.slice(cursor), highlight: false });
  }
  return pieces;
}
