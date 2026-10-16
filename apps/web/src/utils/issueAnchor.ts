import {
  extractQuotedSnippets,
  locateInEssay,
  paragraphHighlightRange,
} from "./essayLocate";
import { mergeHighlightRanges, type HighlightRange } from "./highlightEssay";

type IssueLike = {
  explanation?: string;
  issue_title?: string;
  tag?: string;
  material_ref?: string;
};

function collapseSpaces(s: string): string {
  return s.replace(/\s+/g, "");
}

function shouldAnchorFromExplanation(prob: string): boolean {
  if (extractQuotedSnippets(prob).length > 0) return true;
  return /3\.\s*|误输入|格式残留|格式错误|模版|模板|套话|模板化/.test(prob);
}

function quotedFragmentsInProblem(text: string): string[] {
  const raw = extractQuotedSnippets(text);
  const out: string[] = [];
  const seen = new Set<string>();
  for (const frag of raw) {
    const pieces = [frag, ...frag.split(/[…\.]{2,}/)];
    for (const piece of pieces) {
      const p = piece.trim().replace(/^[，、；：]+|[，、；：]+$/g, "");
      if (p.length < 4 || seen.has(p)) continue;
      seen.add(p);
      out.push(p);
    }
  }
  return out;
}

function findPhrasePos(essay: string, phrase: string): number {
  const p = phrase.trim();
  if (!p) return -1;
  let idx = essay.indexOf(p);
  if (idx >= 0) return idx;
  const pc = collapseSpaces(p);
  const ec = collapseSpaces(essay);
  if (pc.length < 4 || !ec.includes(pc)) return -1;
  const ci = ec.indexOf(pc);
  let raw = 0;
  let col = 0;
  while (raw < essay.length && col < ci) {
    if (!/\s/u.test(essay[raw]!)) col += 1;
    raw += 1;
  }
  return raw;
}

function sentenceContaining(essay: string, pos: number): string {
  pos = Math.max(0, Math.min(essay.length, pos));
  const left = Math.max(
    essay.lastIndexOf("。", pos),
    essay.lastIndexOf("！", pos),
    essay.lastIndexOf("？", pos),
    essay.lastIndexOf("；", pos),
    essay.lastIndexOf("\n", pos),
  );
  const start = left < 0 ? 0 : left + 1;
  const ends = ["。", "！", "？", "；", "\n"]
    .map((ch) => essay.indexOf(ch, pos))
    .filter((x) => x >= 0);
  const end = ends.length ? Math.min(...ends) + 1 : essay.length;
  return essay.slice(start, end).replace(/\s+/g, " ").trim();
}

function locateQuoteSpan(essay: string, quote: string): HighlightRange | null {
  const q = quote.trim();
  if (q.length < 4) return null;
  let idx = essay.indexOf(q);
  if (idx >= 0) return { start: idx, end: idx + q.length, reason: "issue" };
  for (let len = Math.min(q.length, 56); len >= 8; len -= 2) {
    const sub = q.slice(0, len);
    idx = essay.indexOf(sub);
    if (idx >= 0) return { start: idx, end: idx + len, reason: "issue" };
  }
  const pc = collapseSpaces(q);
  const ec = collapseSpaces(essay);
  if (pc.length >= 4 && ec.includes(pc)) {
    const ci = ec.indexOf(pc);
    let raw = 0;
    let col = 0;
    while (raw < essay.length && col < ci) {
      if (!/\s/u.test(essay[raw]!)) col += 1;
      raw += 1;
    }
    return { start: raw, end: Math.min(essay.length, raw + q.length), reason: "issue" };
  }
  return null;
}

function closingTemplateSentence(essay: string): string {
  const re1 =
    /[^。！？\n]{0,24}方能[^。！？\n]{0,36}共建[^。！？\n]{0,36}美[^。！？\n]{0,24}[。！？]/g;
  let m = re1.exec(essay);
  if (m?.[0] && m[0].replace(/\s+/g, " ").trim().length >= 12) {
    return m[0].replace(/\s+/g, " ").trim();
  }
  const re2 =
    /[^。！？\n]{0,12}共建[^。！？\n]{0,36}美[^。！？\n]{0,24}生活[^。！？\n]{0,12}[。！？]/g;
  m = re2.exec(essay);
  if (m?.[0] && m[0].replace(/\s+/g, " ").trim().length >= 12) {
    return m[0].replace(/\s+/g, " ").trim();
  }
  return "";
}

/** 与 grading_helpers._issue_anchor_spans_from_explanation 对齐 */
export function issueAnchorRangesFromExplanation(
  essay: string,
  issue: IssueLike,
): HighlightRange[] {
  const prob = `${issue.explanation ?? ""} ${issue.issue_title ?? ""}`.trim();
  if (!essay.trim()) return [];

  const ranges: HighlightRange[] = [];
  const seen = new Set<string>();

  const add = (hit: HighlightRange | null) => {
    if (!hit || hit.end <= hit.start) return;
    const key = `${hit.start}:${hit.end}`;
    if (seen.has(key)) return;
    seen.add(key);
    ranges.push(hit);
  };

  const paraInProb = prob.match(/第\s*(\d+)\s*段/);
  if (paraInProb) {
    add(paragraphHighlightRange(essay, `第${paraInProb[1]}段`));
  } else if (issue.material_ref && /第\s*\d+\s*段/.test(issue.material_ref)) {
    add(paragraphHighlightRange(essay, issue.material_ref));
  }

  if (!shouldAnchorFromExplanation(prob)) {
    return mergeHighlightRanges(ranges);
  }

  for (const phrase of quotedFragmentsInProblem(prob)) {
    const pos = findPhrasePos(essay, phrase);
    if (pos < 0) continue;
    const sent = sentenceContaining(essay, pos);
    add(locateQuoteSpan(essay, sent));
  }

  if (/模板|套话|模版|方能|口号/.test(prob)) {
    const closing = closingTemplateSentence(essay);
    if (closing) add(locateQuoteSpan(essay, closing));
  }

  if (/3\.|误输入|格式残留|格式错误/.test(prob)) {
    const lineMatch = essay.match(/(?:^|[\n\r])\s*3\.\s*[^\n\r。！？；]{4,}/);
    if (lineMatch) {
      const line = lineMatch[0].trim();
      const idx = essay.indexOf(line);
      if (idx >= 0) add({ start: idx, end: idx + line.length, reason: "issue" });
    }
  }

  return mergeHighlightRanges(ranges);
}

export function primaryIssueAnchorQuote(essay: string, issue: IssueLike): string {
  const ranges = issueAnchorRangesFromExplanation(essay, issue);
  if (!ranges.length) return "";
  const { start, end } = ranges[0]!;
  return essay.slice(start, end).replace(/\s+/g, " ").trim();
}

export function quotePlausibleForExplanation(
  essay: string,
  issue: IssueLike,
  quote: string,
): boolean {
  const prob = `${issue.explanation ?? ""} ${issue.issue_title ?? ""}`;
  if (!shouldAnchorFromExplanation(prob)) return true;
  const q = quote.trim();
  if (!q) return false;
  const anchors = issueAnchorRangesFromExplanation(essay, issue);
  if (!anchors.length) return true;
  const qloc = locateQuoteSpan(essay, q);
  if (!qloc) return false;
  for (const a of anchors) {
    if (qloc.start <= a.end && qloc.end >= a.start) return true;
  }
  return q.length <= 48;
}
