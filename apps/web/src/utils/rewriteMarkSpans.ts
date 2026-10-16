import { locateInEssay } from "./essayLocate";
import {
  issueAnchorRangesFromExplanation,
  quotePlausibleForExplanation,
} from "./issueAnchor";
import { mergeHighlightRanges, type HighlightRange } from "./highlightEssay";

type IssueLike = {
  tag?: string;
  issue_title?: string;
  explanation?: string;
  user_quote?: string;
  evidence_ref?: string;
  material_ref?: string;
  rewrite_mark_spans?: { start: number; end: number }[];
};

type EditSegment = {
  quote?: string;
  source_quote?: string;
  issue_tag?: string;
  reason?: string;
};

function issueTag(issue: IssueLike): string {
  return String(issue.tag ?? issue.issue_title ?? "").trim();
}

function editMatchesIssue(row: EditSegment, issue: IssueLike): boolean {
  const tag = issueTag(issue);
  const itag = String(row.issue_tag ?? "").trim();
  if (itag && tag && (itag === tag || tag.startsWith(itag) || itag.startsWith(tag.split(/\s+/)[0] ?? ""))) {
    return true;
  }
  const reason = String(row.reason ?? "");
  const code = tag.match(/^(Q\d+)/i)?.[1]?.toUpperCase();
  if (code && reason.toUpperCase().includes(code)) return true;
  const label = tag.split(/\s+/).slice(1).join("") || tag;
  return Boolean(label && label.length >= 2 && reason.includes(label));
}

function spansFromIssue(issue: IssueLike): HighlightRange[] {
  const out: HighlightRange[] = [];
  for (const s of issue.rewrite_mark_spans ?? []) {
    if (!Number.isFinite(s.start) || !Number.isFinite(s.end) || s.end <= s.start) continue;
    out.push({ start: s.start, end: s.end, reason: issueTag(issue) });
  }
  return out;
}

function inferSpanFromEdit(essay: string, issue: IssueLike, row: EditSegment): HighlightRange | null {
  const candidates = [row.source_quote, issue.user_quote].filter(Boolean) as string[];
  for (const q of candidates) {
    const hit = locateInEssay(essay, [q], { reason: issueTag(issue) });
    if (hit) return hit;
  }
  return null;
}

/** 单条问题在正文中的全部待改区间 */
export function highlightRangesForIssue(
  essay: string,
  issue: IssueLike,
  editSegments?: EditSegment[],
): HighlightRange[] {
  if (!essay.trim()) return [];

  const fromSpans = spansFromIssue(issue);
  if (fromSpans.length) return mergeHighlightRanges(fromSpans);

  const fromExplanation = issueAnchorRangesFromExplanation(essay, issue);
  if (fromExplanation.length) return fromExplanation;

  const reason = issueTag(issue);
  const quote = String(issue.user_quote ?? "").trim();
  if (quote && quotePlausibleForExplanation(essay, issue, quote)) {
    const fromQuote = locateInEssay(
      essay,
      [issue.user_quote, issue.evidence_ref],
      { materialRef: issue.material_ref, reason },
    );
    if (fromQuote) return [fromQuote];
  }

  if (editSegments?.length) {
    for (const row of editSegments) {
      if (!editMatchesIssue(row, issue)) continue;
      const hit = inferSpanFromEdit(essay, issue, row);
      if (hit) return [hit];
    }
  }
  return [];
}

/** 单条问题在正文中的主对应区间（摘录区用） */
export function highlightRangeForIssue(
  essay: string,
  issue: IssueLike,
  editSegments?: EditSegment[],
): HighlightRange | null {
  const ranges = highlightRangesForIssue(essay, issue, editSegments);
  return ranges[0] ?? null;
}

/** 「本稿原文」标红：汇总各问题在正文中的待改区间 */
export function collectEssayRewriteMarkRanges(
  essay: string,
  issues: IssueLike[],
  editSegments?: EditSegment[],
): HighlightRange[] {
  if (!essay.trim()) return [];
  const ranges: HighlightRange[] = [];

  for (const issue of issues) {
    ranges.push(...highlightRangesForIssue(essay, issue, editSegments));
  }

  return mergeHighlightRanges(ranges);
}
