import { primaryIssueAnchorQuote } from "./issueAnchor";

type Issue = {
  tag?: string;
  issue_title?: string;
  explanation?: string;
  user_quote?: string;
  solution_example?: string;
};

function isRepeatStructureIssue(issue: Issue): boolean {
  const p = `${issue.explanation ?? ""} ${issue.issue_title ?? ""}`;
  return /重复|递进|第四段|信息增量|与前文|交叉|功能重叠/.test(p);
}

function extractParallelRoles(q: string): string[] {
  const m = q.match(/无论(.+?)还是(.+?)，/);
  if (!m) return [];
  const left = m[1] ?? "";
  const right = (m[2] ?? "").trim();
  const roles = left
    .split(/[、,，]/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (right) roles.push(right);
  return roles;
}

/** 与后端 _concrete_rewrite_for_repeat 对齐 */
function rewriteForRepeatQuote(q: string): string {
  const roles = extractParallelRoles(q);
  if (roles.length >= 3) {
    return `${roles[0]}在技艺上精益求精，${roles[1]}在一线补齐短板，${roles[2]}在本职上久久为功；三者同向发力，把专注与坚守汇成可感的生活秩序。`;
  }
  if (roles.length === 2) {
    return `${roles[0]}侧重打磨精度，${roles[1]}侧重修补漏洞；本段用一句因果分析收束，并与上段案例形成递进。`;
  }
  const fillers = [
    "无论",
    "都应摒弃急功近利心态，",
    "把自己的领域当作耕耘的田野，",
    "以久久为功的专注",
    "让默默付出汇成",
  ];
  let s = q;
  for (const ph of fillers) {
    s = s.split(ph).join("");
  }
  s = s.replace(/[，,\s]{2,}/g, "，").replace(/^[，。；\s]+|[，。；\s]+$/g, "");
  if (s.length >= 18) {
    return `${s.replace(/[，。；]+$/, "")}，并归结到可感的生活秩序。`;
  }
  return "工匠、干部与从业者各就其位：精益求精、补齐短板、久久为功，共同托举温暖笃定的生活秩序。";
}

type EditSegment = {
  quote?: string;
  reason?: string;
  issue_tag?: string;
  source_quote?: string;
};

type RewriteDemoLike = {
  rewrite_text?: string;
  edit_segments?: EditSegment[];
  change_summary?: string[];
  validation_check?: {
    issue_fix_status?: {
      tag?: string;
      edit_indexes?: number[];
    }[];
  };
};

function editMatchesIssue(row: EditSegment, issue: Issue): boolean {
  const tag = (issue.tag ?? issue.issue_title ?? "").trim();
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

function extractChangeFragments(oldText: string, newText: string): { news: string[]; olds: string[] } {
  const olds: string[] = [];
  const news: string[] = [];
  if (!newText.trim()) return { news, olds };

  const o = oldText.replace(/\s+/g, " ");
  const n = newText.replace(/\s+/g, " ");
  if (!o) return { news: [n.trim()].filter((x) => x.length >= 2), olds };

  const max = Math.max(o.length, n.length);
  let i = 0;
  while (i < max && o[i] === n[i]) i += 1;
  let j = 0;
  while (j < max - i && o[o.length - 1 - j] === n[n.length - 1 - j]) j += 1;
  const oldMid = o.slice(i, o.length - j || undefined).trim("，、；： ");
  const newMid = n.slice(i, n.length - j || undefined).trim("，、；： ");
  if (newMid.length >= 2) news.push(newMid);
  if (oldMid.length >= 2) olds.push(oldMid);
  return { news, olds };
}

function formatCompactExample(news: string[], _olds: string[]): string | null {
  const newBody = news.join(" ").trim();
  if (newBody.length < 2) return null;
  const body = newBody.length > 220 ? `${newBody.slice(0, 217)}…` : newBody;
  return `改写示例：「${body}」`;
}

function formatEditRow(row: EditSegment, issue: Issue): string | null {
  const rewriteQ = row.quote?.trim();
  if (!rewriteQ || rewriteQ.length < 4) return null;
  if (rewriteQ.length >= 16) {
    const body = rewriteQ.length > 220 ? `${rewriteQ.slice(0, 217)}…` : rewriteQ;
    return `改写示例：「${body}」`;
  }
  const source = String(row.source_quote ?? issue.user_quote ?? "").trim();
  const { news, olds } = extractChangeFragments(source, rewriteQ);
  return formatCompactExample(news.length ? news : [rewriteQ], olds);
}

function locateQuoteSpan(text: string, quote: string): { start: number; end: number } | null {
  const q = quote.trim();
  if (q.length < 6) return null;
  let idx = text.indexOf(q);
  if (idx >= 0) return { start: idx, end: idx + q.length };
  for (let len = Math.min(q.length, 56); len >= 8; len -= 2) {
    const sub = q.slice(0, len);
    idx = text.indexOf(sub);
    if (idx >= 0) return { start: idx, end: idx + len };
  }
  return null;
}

function sentenceAt(text: string, pos: number): string {
  pos = Math.max(0, Math.min(text.length, pos));
  const left = Math.max(text.lastIndexOf("。", pos), text.lastIndexOf("！", pos), text.lastIndexOf("？", pos));
  const start = left < 0 ? 0 : left + 1;
  const rights = ["。", "！", "？", "\n"].map((ch) => text.indexOf(ch, pos)).filter((x) => x >= 0);
  const end = rights.length ? Math.min(...rights) + 1 : text.length;
  return text.slice(start, end).replace(/\s+/g, " ").trim();
}

function rewriteExampleNearQuote(original: string, rewrite: string, quote: string): string | null {
  const span = locateQuoteSpan(original, quote);
  if (!span) return null;
  const anchor = original.slice(span.start, span.end);
  if (!rewrite.includes(anchor)) {
    const prefix = original.slice(Math.max(0, span.start - 24), span.start);
    const pi = prefix ? rewrite.indexOf(prefix) : -1;
    if (pi >= 0) {
      const rs = pi + prefix.length;
      const oSent = sentenceAt(original, span.start);
      const rSent = sentenceAt(rewrite, rs);
      if (rSent && oSent && rSent !== oSent) {
        const { news, olds } = extractChangeFragments(oSent, rSent);
        return formatCompactExample(news, olds);
      }
    }
    return null;
  }
  const rpos = rewrite.indexOf(anchor);
  const oSent = sentenceAt(original, span.start);
  const rSent = sentenceAt(rewrite, rpos);
  if (rSent && oSent && rSent !== oSent) {
    const { news, olds } = extractChangeFragments(oSent, rSent);
    return formatCompactExample(news, olds);
  }
  return null;
}

function fromEditSegments(issue: Issue, rewriteDemo: RewriteDemoLike | undefined): string | null {
  const edits = rewriteDemo?.edit_segments ?? [];
  const tag = (issue.tag ?? "").trim();

  const fixRow = rewriteDemo?.validation_check?.issue_fix_status?.find(
    (r) => r.tag === tag || (tag && String(r.tag ?? "").startsWith(tag.split(/\s+/)[0] ?? "")),
  );
  if (fixRow?.edit_indexes?.length) {
    const lines = fixRow.edit_indexes
      .map((n) => formatEditRow(edits[n - 1] ?? {}, issue))
      .filter(Boolean) as string[];
    if (lines.length) return lines.join("\n\n");
  }

  for (const row of edits) {
    if (editMatchesIssue(row, issue)) {
      const line = formatEditRow(row, issue);
      if (line) return line;
    }
  }
  return null;
}

function overlapRatio(a: string, b: string): number {
  if (!a || !b) return 0;
  const short = a.length <= b.length ? a : b;
  const long = a.length <= b.length ? b : a;
  let best = 0;
  for (let i = 0; i <= long.length - short.length; i += Math.max(1, Math.floor(short.length / 8))) {
    let n = 0;
    for (let j = 0; j < short.length; j++) {
      if (short[j] === long[i + j]) n += 1;
    }
    best = Math.max(best, n / short.length);
  }
  return best;
}

function shrinkLongExampleLine(text: string, issue: Issue, _essayContent: string): string {
  const m = text.match(/「([^」]{20,})」/);
  if (!m) return text;
  const inner = m[1].trim();
  if (inner.length <= 88) return text;
  const quote = String(issue.user_quote ?? "").trim();
  if (quote && overlapRatio(quote, inner) < 0.45) {
    const clause = inner.split(/[，；。]/)[0]?.trim();
    if (clause && clause.length >= 6) {
      const body = clause.length > 56 ? `${clause.slice(0, 53)}…` : clause;
      return `改写示例：「${body}」`;
    }
  }
  const { news, olds } = extractChangeFragments(quote, inner);
  const compact = formatCompactExample(news.length ? news : [inner.slice(0, 80)], olds);
  return compact ?? text;
}

const GENERIC_SOLUTION_MARKERS = [
  "精细治理",
  "听得到诉求",
  "看得见变化",
  "管得住风险",
  "网格议事",
  "以某县",
  "以某社区",
  "王弼所谓",
  "源头活水",
];

/** 修改示例须与问题引用/说明相关，否则不展示 ! */
export function solutionExampleRelatesToIssue(issue: Issue, text: string): boolean {
  const raw = text.trim();
  if (!raw) return false;
  const quote = String(issue.user_quote ?? "").trim();
  const prob = String(issue.explanation ?? issue.issue_title ?? "").trim();
  const innerMatch = raw.match(/「([^」]{4,})」/);
  const inner = innerMatch?.[1]?.trim() ?? raw.replace(/^改写示例[：:]\s*/, "").trim();

  if (GENERIC_SOLUTION_MARKERS.some((g) => raw.includes(g))) {
    if (quote && !GENERIC_SOLUTION_MARKERS.some((g) => quote.includes(g))) {
      if (!prob || !GENERIC_SOLUTION_MARKERS.some((g) => prob.includes(g))) return false;
    }
  }

  if (quote.length < 8) return true;
  if (overlapRatio(quote, inner) >= 0.08) return true;
  for (let n = Math.min(quote.length, 52); n >= 6; n -= 2) {
    const sub = quote.slice(0, n);
    if (inner.includes(sub) || raw.includes(sub)) return true;
  }
  for (const run of quote.match(/[\u4e00-\u9fff]{3,}/g) ?? []) {
    if (inner.includes(run) || raw.includes(run)) return true;
  }
  for (const run of prob.match(/[\u4e00-\u9fff]{3,}/g) ?? []) {
    if (inner.includes(run)) return true;
  }
  return false;
}

function exampleAlignsWithUserQuote(issue: Issue, text: string): boolean {
  const quote = String(issue.user_quote ?? "")
    .trim()
    .replace(/^「|」$/g, "");
  if (quote.length < 8) return true;
  const innerMatch = text.match(/「([^」]{4,})」/);
  const inner = innerMatch?.[1]?.trim() ?? text.replace(/^改写示例[：:]\s*/, "").trim();
  if (overlapRatio(quote, inner) >= 0.12) return true;
  for (let n = Math.min(quote.length, 48); n >= 6; n -= 2) {
    if (inner.includes(quote.slice(0, n))) return true;
  }
  for (const run of quote.match(/[\u4e00-\u9fff]{3,}/g) ?? []) {
    if (inner.includes(run)) return true;
  }
  return false;
}

function acceptSolutionHint(issue: Issue, hint: string, essayContent: string): string {
  const t = hint.trim();
  if (!t) return "";
  if (!exampleAlignsWithUserQuote(issue, t) && !isRepeatStructureIssue(issue)) return "";
  const preset = String(issue.solution_example ?? "").trim();
  const trustServer = preset.length > 0 && (t === preset || preset.includes(t) || t.includes(preset));
  const looksLikeFullRewrite = /^改写示例[：:]?\s*「[^」]{12,}」/.test(t);
  if (!trustServer && !looksLikeFullRewrite && !solutionExampleRelatesToIssue(issue, t)) return "";
  const out = shrinkLongExampleLine(t, issue, essayContent);
  return out || t;
}

function sentenceContainingPos(essay: string, pos: number): string {
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

/** 问题说明点名的正文句（套话/误输等），优先于无关摘录 */
function resolveAnchorFromExplanation(issue: Issue, essay: string): string {
  const p = `${issue.explanation ?? ""} ${issue.issue_title ?? ""}`;
  if (!/语言|格式|模版|模板|套话|3\.|误输入|规范性/.test(p)) return "";
  const quoted = [...p.matchAll(/[「『]([^」』]{4,48})[」』]/g)].map((m) => m[1].trim());
  for (const phrase of quoted) {
    if (essay.includes(phrase)) return sentenceContainingPos(essay, essay.indexOf(phrase));
  }
  const tpl = "方能共建温暖、安定、美好的生活家园";
  if (p.includes("方能共建") && essay.includes(tpl)) {
    return sentenceContainingPos(essay, essay.indexOf(tpl));
  }
  const m3 = essay.match(/(?:^|\n)\s*3\.\s*[^\n。！？；]{4,}/);
  if (m3 && /3\.|误输入|格式/.test(p)) return m3[0].trim();
  return "";
}

function rewriteLanguageTargetSentence(target: string): string {
  let out = target;
  const replacements: [string, string][] = [
    ["方能共建温暖、安定、美好的生活家园", "从而托举温暖笃定的生活秩序"],
    ["共建温暖、安定、美好的生活家园", "让生活秩序更可感、更可持续"],
  ];
  for (const [a, b] of replacements) {
    if (out.includes(a)) out = out.replace(a, b);
  }
  out = out.replace(/^\s*3\.\s*/, "").replace(/；正说明/g, "，可见").replace(/这一领域，/g, "");
  if (!out.endsWith("。")) out = `${out.replace(/[，；]+$/, "")}。`;
  return out;
}

/** 与后端 _infer_issue_solution_from_context 对齐的本地兜底（报告未带 solution_example 时） */
function inferLocalRewriteExample(issue: Issue, essayContent = ""): string {
  const p = `${issue.explanation ?? ""} ${issue.issue_title ?? ""}`;
  const essay = essayContent.trim();
  let q = String(issue.user_quote ?? "")
    .trim()
    .replace(/^「|」$/g, "");
  if (!q && essay) {
    q = primaryIssueAnchorQuote(essay, issue);
  }

  if (isRepeatStructureIssue(issue) && q.length >= 8) {
    return `改写示例：「${rewriteForRepeatQuote(q)}」`;
  }

  if (essay) {
    const anchor = resolveAnchorFromExplanation(issue, essay);
    if (anchor.length >= 8) {
      return `改写示例：「${rewriteLanguageTargetSentence(anchor)}」`;
    }
  }

  if (q.length < 8) {
    if (essay && /模版|模板|套话|方能共建|3\.|误输入|格式/.test(p)) {
      const templatePhrase = p.match(/[「『]([^」』]{4,40})[」』]/)?.[1]?.trim();
      if (templatePhrase && essay.includes(templatePhrase)) {
        const idx = essay.indexOf(templatePhrase);
        const start = Math.max(essay.lastIndexOf("。", idx), essay.lastIndexOf("；", idx), 0);
        const end = essay.indexOf("。", idx);
        const sent = essay.slice(start > 0 ? start + 1 : start, end > idx ? end + 1 : idx + templatePhrase.length + 24);
        if (sent.includes(templatePhrase)) {
          return `改写示例：「${sent.replace(templatePhrase, "从而托举温暖笃定的生活秩序")}」`;
        }
      }
      const m3 = essay.match(/(?:^|\n)\s*3\.\s*[^\n。！？]{4,}/);
      if (m3 && /3\.|误输入|格式/.test(p)) {
        const fixed = m3[0].trim().replace(/^\s*3\.\s*/, "");
        if (fixed.length >= 8) return `改写示例：「${fixed}」`;
      }
    }
    return "";
  }

  if (/3\.|误输入|格式/.test(p)) {
    const fixed = q.replace(/^\s*3\.\s*/, "").trim();
    if (fixed !== q && fixed.length >= 8) return `改写示例：「${fixed}」`;
  }

  if (/模版|模板|套话|口号/.test(p)) {
    const replacements: [string, string][] = [
      ["方能共建温暖、安定、美好的生活家园", "从而托举温暖笃定的生活秩序"],
      ["共建温暖、安定、美好的生活家园", "让生活秩序更可感、更可持续"],
      ["让默默付出汇成生活的笃定", "让默默付出转化为可检验的生活秩序"],
    ];
    let out = q;
    for (const [a, b] of replacements) {
      if (out.includes(a)) out = out.replace(a, b);
    }
    if (out !== q) return `改写示例：「${out}」`;
  }

  if (/语言|格式|规范性|模版|模板|套话|误输入|3\./.test(p)) {
    let s = q.replace(/^\s*3\.\s*/, "").trim();
    const reps: [string, string][] = [
      ["这一领域，", ""],
      ["针对", "面向"],
      ["让群众在家门口就能看病", "使群众就近可及就医"],
      ["；正说明", "，可见"],
      ["正说明", "可见"],
      ["等政策，", "等举措，"],
    ];
    for (const [a, b] of reps) {
      if (s.includes(a)) s = s.replace(a, b);
    }
    s = s.replace(/[，；]+$/, "");
    if (s.length >= 12) {
      const body = s.endsWith("。") ? s : `${s}。`;
      if (body !== q && body !== `${q}。`) return `改写示例：「${body}」`;
      if (q.includes("；")) return `改写示例：「${q.replace("；", "，")}」`;
    }
  }

  return "";
}

function matchedSuggestion(issue: Issue, suggestions: string[]): string {
  const title = String(issue.issue_title ?? "").trim();
  const expl = String(issue.explanation ?? "").trim();
  const probe = title || expl;
  if (!probe) return "";
  let best = "";
  let bestScore = 0;
  for (const raw of suggestions) {
    const t = String(raw ?? "").trim();
    if (t.length < 8) continue;
    let score = 0;
    const head = probe.slice(0, 10);
    if (head.length >= 4 && t.includes(head)) score += 3;
    for (const word of probe.split(/[^\u4e00-\u9fffA-Za-z0-9]+/).filter((w) => w.length >= 2)) {
      if (t.includes(word)) score += 1;
    }
    if (score > bestScore) {
      bestScore = score;
      best = t;
    }
  }
  return bestScore >= 2 ? best : "";
}

/** 悬停展示用：仅返回可直接阅读的改写示例，无则返回空（不展示 ! 标识） */
export function issueSolutionExampleText(
  issue: Issue,
  rewriteDemo: RewriteDemoLike | undefined,
  suggestions: string[],
  index: number,
  essayContent: string,
  opts?: { shortOnly?: boolean },
): string {
  const preset = String(issue.solution_example ?? "").trim();
  if (preset) {
    const ok = acceptSolutionHint(issue, preset, essayContent);
    if (ok) return ok;
  }

  if (opts?.shortOnly) {
    const fromEdits = fromEditSegments(issue, rewriteDemo);
    if (fromEdits) {
      const ok = acceptSolutionHint(issue, fromEdits, essayContent);
      if (ok) return ok;
    }
    const sug = (suggestions[index] ?? matchedSuggestion(issue, suggestions)).trim();
    if (sug && sug.length >= 8) {
      const raw = sug.startsWith("改写") ? sug : `改写示例：${sug}`;
      const ok = acceptSolutionHint(issue, raw, essayContent);
      if (ok) return ok;
    }
    const localShort = inferLocalRewriteExample(issue, essayContent);
    if (localShort) {
      const ok = acceptSolutionHint(issue, localShort, essayContent);
      if (ok) return ok;
    }
    return "";
  }

  const fromEdits = fromEditSegments(issue, rewriteDemo);
  if (fromEdits) {
    const ok = acceptSolutionHint(issue, fromEdits, essayContent);
    if (ok) return ok;
  }

  const rewrite = rewriteDemo?.rewrite_text?.trim();
  const quote = String(issue.user_quote ?? "").trim();
  if (rewrite && essayContent && quote) {
    const near = rewriteExampleNearQuote(essayContent, rewrite, quote);
    if (near) {
      const ok = acceptSolutionHint(issue, near, essayContent);
      if (ok) return ok;
    }
  }

  const summaries = rewriteDemo?.change_summary ?? [];
  const tag = (issue.tag ?? "").trim();
  for (const line of summaries) {
    const t = String(line).trim();
    if (t.length >= 10 && tag && (t.includes(tag.split(/\s+/)[0] ?? "") || t.includes(tag))) {
      const raw = t.startsWith("改写") ? t : `改写示例：${t}`;
      const ok = acceptSolutionHint(issue, raw, essayContent);
      if (ok) return ok;
    }
  }

  const sug = (suggestions[index] ?? matchedSuggestion(issue, suggestions)).trim();
  if (sug && sug.length >= 8) {
    const raw = sug.startsWith("改写") ? sug : `改写示例：${sug}`;
    const ok = acceptSolutionHint(issue, raw, essayContent);
    if (ok) return ok;
  }

  const local = inferLocalRewriteExample(issue, essayContent);
  if (local) {
    const ok = acceptSolutionHint(issue, local, essayContent);
    if (ok) return ok;
  }

  return "";
}
