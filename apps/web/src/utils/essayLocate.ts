import type { HighlightRange } from "./highlightEssay";
import { trimRangesToMaxCoverage } from "./highlightEssay";

function collapseSpaces(s: string): string {
  return s.replace(/\s+/g, "");
}

/** 从说明文字中提取可检索的原文引号片段 */
export function extractQuotedSnippets(text: string | undefined): string[] {
  if (!text?.trim()) return [];
  const out: string[] = [];
  const patterns = [/「([^」]{4,240})」/g, /“([^”]{4,240})”/g, /"([^"]{4,240})"/g];
  for (const re of patterns) {
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      const seg = m[1]?.trim();
      if (seg) out.push(seg);
    }
  }
  return out;
}

function looksLikeMaterialRef(ref: string): boolean {
  const t = ref.trim();
  if (!t) return true;
  return /^材料\s*\d|^给定材料|^资料\s*\d|^第?\s*\d+\s*则材料/.test(t);
}

function tryIndexRange(content: string, quote: string, reason?: string): HighlightRange | null {
  const q = quote.trim();
  if (q.length < 4) return null;
  let idx = content.indexOf(q);
  if (idx >= 0) return { start: idx, end: idx + q.length, reason };

  const collapsedContent = collapseSpaces(content);
  const collapsedQuote = collapseSpaces(q);
  if (collapsedQuote.length >= 4) {
    idx = collapsedContent.indexOf(collapsedQuote);
    if (idx >= 0) {
      // map collapsed index back approximately by scanning
      let rawIdx = 0;
      let colIdx = 0;
      while (colIdx < idx && rawIdx < content.length) {
        if (!/\s/u.test(content[rawIdx]!)) colIdx += 1;
        rawIdx += 1;
      }
      const end = rawIdx + q.length;
      return { start: rawIdx, end: Math.min(content.length, end), reason };
    }
  }

  for (let len = Math.min(q.length, 48); len >= 8; len -= 2) {
    const sub = q.slice(0, len);
    idx = content.indexOf(sub);
    if (idx >= 0) return { start: idx, end: idx + sub.length, reason };
  }
  return null;
}

/** 按「第 N 段」在正文中圈选第 N 个段首块（含标题后首段为 1） */
export function paragraphHighlightRange(content: string, materialRef: string): HighlightRange | null {
  const m = materialRef.match(/第\s*(\d+)\s*段/);
  if (!m) return null;
  const want = Number(m[1]);
  if (!Number.isFinite(want) || want < 1) return null;

  const normalized = content.replace(/\r\n/g, "\n");
  const paraStarts: { start: number; end: number }[] = [];
  let cursor = 0;
  let afterBlank = true;
  for (const line of normalized.split("\n")) {
    const start = cursor;
    const end = start + line.length;
    cursor = end + 1;
    if (!line.trim()) {
      afterBlank = true;
      continue;
    }
    if (afterBlank) {
      paraStarts.push({ start, end });
      afterBlank = false;
    } else {
      afterBlank = false;
    }
  }
  const hit = paraStarts[want - 1];
  if (!hit) return null;
  let end = hit.end;
  const next = paraStarts[want];
  if (next) end = next.start - 1;
  else end = normalized.length;
  return { start: hit.start, end: Math.max(hit.start + 1, end), reason: materialRef };
}

export function locateInEssay(
  content: string,
  candidates: (string | undefined | null)[],
  opts?: { materialRef?: string; reason?: string },
): HighlightRange | null {
  if (!content.trim()) return null;

  const reason = opts?.reason;
  for (const raw of candidates) {
    const q = String(raw ?? "").trim();
    if (!q || looksLikeMaterialRef(q)) continue;
    const hit = tryIndexRange(content, q, reason);
    if (hit) return hit;
  }

  for (const raw of candidates) {
    for (const seg of extractQuotedSnippets(String(raw ?? ""))) {
      const hit = tryIndexRange(content, seg, reason);
      if (hit) return hit;
    }
  }

  if (opts?.materialRef) {
    const para = paragraphHighlightRange(content, opts.materialRef);
    if (para) return para;
  }

  return null;
}

const EXCERPT_MAX = 88;
const EXCERPT_HEAD = 32;
const EXCERPT_TAIL = 32;

function normalizeExcerptBody(text: string): string {
  return text.replace(/\r\n/g, "\n").replace(/\n+/g, " ").replace(/\s+/g, " ").trim();
}

/** 展示用：「原文摘录」（过长中间省略，仅用于作文正文） */
export function formatFeedbackEssayExcerpt(raw: string): string {
  const body = normalizeExcerptBody(raw);
  if (!body) return "";
  if (body.length <= EXCERPT_MAX) {
    return `「${body}」`;
  }
  return `「${body.slice(0, EXCERPT_HEAD)}……${body.slice(-EXCERPT_TAIL)}」`;
}

function excerptFromHit(content: string, hit: HighlightRange): string | null {
  const slice = normalizeExcerptBody(content.slice(hit.start, hit.end));
  if (slice.length < 4) return null;
  return formatFeedbackEssayExcerpt(slice);
}

const CRITIQUE_FRAGMENT = /缺乏|不足|重合|偏离|建议|应当|过于|未|勿|不要|不宜|避免/;

/** 从评语里找能在正文中命中的短语（不把整段评语当原文） */
function findEssaySnippetFromHint(content: string, hint: string): HighlightRange | null {
  if (!hint.trim()) return null;
  const runs: string[] = [];
  const re = /[\u4e00-\u9fffA-Za-z0-9，、；：]{8,48}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(hint)) !== null) {
    const run = m[0];
    if (!CRITIQUE_FRAGMENT.test(run)) runs.push(run);
  }
  runs.sort((a, b) => b.length - a.length);
  for (const run of runs) {
    const hit = tryIndexRange(content, run);
    if (hit) return hit;
  }
  return null;
}

/** 从作答正文解析与评语对应的可识别原文摘录（禁止回显评语本身） */
export function resolveFeedbackEssayExcerpt(
  content: string,
  directQuotes: (string | undefined | null)[],
  searchHints?: (string | undefined | null)[],
  opts?: { materialRef?: string },
): string | null {
  if (!content.trim()) return null;

  for (const raw of directQuotes) {
    const q = String(raw ?? "").trim();
    if (q.length < 4 || looksLikeMaterialRef(q)) continue;
    const hit = tryIndexRange(content, q);
    if (hit) {
      const out = excerptFromHit(content, hit);
      if (out) return out;
    }
  }

  for (const raw of searchHints ?? []) {
    for (const seg of extractQuotedSnippets(String(raw ?? ""))) {
      const hit = tryIndexRange(content, seg);
      if (hit) {
        const out = excerptFromHit(content, hit);
        if (out) return out;
      }
    }
  }

  for (const raw of searchHints ?? []) {
    const hit = findEssaySnippetFromHint(content, String(raw ?? ""));
    if (hit) {
      const out = excerptFromHit(content, hit);
      if (out) return out;
    }
  }

  const hit = locateInEssay(content, directQuotes, opts);
  if (hit) return excerptFromHit(content, hit);

  if (opts?.materialRef) {
    const para = paragraphHighlightRange(content, opts.materialRef);
    if (para) return excerptFromHit(content, para);
  }

  return null;
}

export type IssueExcerptDisplay = {
  body: string;
  ranges: HighlightRange[];
};

function excerptBodyFromHit(content: string, hit: HighlightRange): string {
  return normalizeExcerptBody(content.slice(hit.start, hit.end));
}

/** 问题卡片原文区：相对摘录内对「待改原文」标红 */
export function resolveIssueExcerptDisplay(
  content: string,
  directQuotes: (string | undefined | null)[],
  searchHints?: (string | undefined | null)[],
  opts?: {
    materialRef?: string;
    markSpans?: { start: number; end: number }[];
  },
): IssueExcerptDisplay | null {
  if (!content.trim()) return null;

  const quoteCandidates = directQuotes.filter((q) => String(q ?? "").trim().length >= 4);
  let hit = locateInEssay(content, quoteCandidates, {
    materialRef: opts?.materialRef,
    reason: "issue",
  });
  const marks = (opts?.markSpans ?? []).filter(
    (s) => Number.isFinite(s.start) && Number.isFinite(s.end) && s.end > s.start,
  );

  if (!hit && marks.length) {
    const start = Math.min(...marks.map((m) => m.start));
    const end = Math.max(...marks.map((m) => m.end));
    hit = { start, end, reason: "issue" };
  }

  if (!hit) {
    const legacy = resolveFeedbackEssayExcerpt(content, directQuotes, searchHints, {
      materialRef: opts?.materialRef,
    });
    if (!legacy) return null;
    const inner = legacy.replace(/^「/, "").replace(/」$/, "");
    return { body: inner, ranges: [] };
  }

  const rangeStart = hit.start;
  const rangeEnd = hit.end;
  let body = excerptBodyFromHit(content, hit);

  if (body.length > EXCERPT_MAX) {
    const head = normalizeExcerptBody(content.slice(hit.start, hit.start + EXCERPT_HEAD + 40));
    const tailLen = EXCERPT_TAIL + 40;
    const tail = normalizeExcerptBody(content.slice(hit.end - tailLen, hit.end));
    body = `${head.slice(0, EXCERPT_HEAD)}……${tail.slice(-EXCERPT_TAIL)}`;
  }

  const relRanges: HighlightRange[] = [];
  for (const m of marks) {
    if (m.end <= rangeStart || m.start >= rangeEnd) continue;
    const rs = Math.max(rangeStart, m.start) - rangeStart;
    const re = Math.min(rangeEnd, m.end) - rangeStart;
    if (re > rs) relRanges.push({ start: rs, end: re, reason: "待改" });
  }

  if (!relRanges.length && searchHints?.length) {
    for (const raw of searchHints) {
      for (const seg of extractQuotedSnippets(String(raw ?? ""))) {
        const idx = body.indexOf(seg);
        if (idx >= 0) {
          relRanges.push({ start: idx, end: idx + seg.length, reason: "待改" });
        } else {
          const collapsedBody = collapseSpaces(body);
          const collapsedSeg = collapseSpaces(seg);
          if (collapsedSeg.length >= 2) {
            const cIdx = collapsedBody.indexOf(collapsedSeg);
            if (cIdx >= 0) {
              relRanges.push({
                start: cIdx,
                end: Math.min(body.length, cIdx + seg.length),
                reason: "待改",
              });
            }
          }
        }
      }
    }
  }

  const mapped = trimRangesToMaxCoverage(body, relRanges, 0.55);
  return { body, ranges: mapped };
}
