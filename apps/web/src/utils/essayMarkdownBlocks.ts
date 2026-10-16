/** 用户作答 Markdown：逐行保留换行/空行，识别 ATX 标题，段首缩进与原文一致 */

export type EssayLayoutLineKind = "empty" | "heading" | "body";

export type EssayLayoutLine = {
  start: number;
  end: number;
  text: string;
  kind: EssayLayoutLineKind;
  headingLevel?: 1 | 2 | 3 | 4 | 5 | 6;
  markdownPrefixLen: number;
  /** 段首行（上一行为空或文首） */
  isParagraphStart: boolean;
};

export function hasLeadingIndent(line: string): boolean {
  return /^([\u3000]{1,2}| {2,})/.test(line);
}

export function parseAtxHeadingLine(line: string): {
  level: 1 | 2 | 3 | 4 | 5 | 6;
  body: string;
  prefixLen: number;
} | null {
  const m = line.match(/^(#{1,6})([ \t]+)(.+)$/);
  if (!m) return null;
  const level = Math.min(6, Math.max(1, m[1].length)) as 1 | 2 | 3 | 4 | 5 | 6;
  return { level, body: m[3], prefixLen: m[1].length + m[2].length };
}

export function isPlainTitleLine(line: string): boolean {
  const t = line.trim();
  if (!t || t.startsWith("#")) return false;
  return t.length <= 48 && !/[。！？；]/.test(t);
}

export type SplitEssayLayoutOptions = {
  /** 为 false 时仅识别 # 标题，不把短行当居中标题（与上传原文一致） */
  inferPlainTitleAsHeading?: boolean;
};

/** 按原文换行拆行，offset 与 content 一致（便于高亮定位） */
export function splitEssayLayoutLines(
  content: string,
  opts?: SplitEssayLayoutOptions,
): EssayLayoutLine[] {
  const inferPlainTitle = opts?.inferPlainTitleAsHeading !== false;
  const normalized = content.replace(/\r\n/g, "\n");
  if (!normalized) return [];

  const rawLines = normalized.split("\n");
  const lines: EssayLayoutLine[] = [];
  let cursor = 0;
  let afterBlank = true;

  for (const line of rawLines) {
    const start = cursor;
    const end = start + line.length;
    cursor = end + 1;

    if (!line.trim()) {
      lines.push({
        start,
        end,
        text: line,
        kind: "empty",
        markdownPrefixLen: 0,
        isParagraphStart: false,
      });
      afterBlank = true;
      continue;
    }

    const atx = parseAtxHeadingLine(line);
    if (atx) {
      lines.push({
        start,
        end,
        text: line,
        kind: "heading",
        headingLevel: atx.level,
        markdownPrefixLen: atx.prefixLen,
        isParagraphStart: false,
      });
      afterBlank = false;
      continue;
    }

    if (inferPlainTitle && afterBlank && isPlainTitleLine(line) && !hasLeadingIndent(line)) {
      lines.push({
        start,
        end,
        text: line,
        kind: "heading",
        headingLevel: 1,
        markdownPrefixLen: 0,
        isParagraphStart: false,
      });
      afterBlank = false;
      continue;
    }

    lines.push({
      start,
      end,
      text: line,
      kind: "body",
      markdownPrefixLen: 0,
      isParagraphStart: afterBlank,
    });
    afterBlank = false;
  }

  return lines;
}

function restoreReferenceHeadings(refLines: string[], alignedLines: string[]): string[] {
  const layout = splitEssayLayoutLines(refLines.join("\n"));
  return refLines.map((refLine, idx) => {
    const row = layout[idx];
    const fromText = alignedLines[idx] ?? "";
    if (!refLine.trim()) {
      return fromText;
    }
    if (row?.kind !== "heading") {
      return fromText;
    }
    const refBody = refLine.slice(row.markdownPrefixLen).trim();
    const textBody = fromText.replace(/^#{1,6}\s+/, "").trim();
    if (!textBody) {
      return refLine;
    }
    if (isPlainTitleLine(textBody) || parseAtxHeadingLine(fromText.trim())) {
      return fromText;
    }
    return refLine;
  });
}

/** 将改写正文按参考作答的空行结构对齐（行数与空行位置一致；标题行不被正文挤占） */
export function alignTextToLineLayout(reference: string, text: string): string {
  const refLines = reference.replace(/\r\n/g, "\n").split("\n");
  const bodyLines = text.replace(/\r\n/g, "\n").split("\n");

  if (refLines.length === bodyLines.length) {
    return restoreReferenceHeadings(refLines, bodyLines).join("\n");
  }

  const layout = splitEssayLayoutLines(reference.replace(/\r\n/g, "\n"));
  const contentQueue = bodyLines.filter((l) => l.trim());
  let qi = 0;
  let layoutIdx = 0;
  const out: string[] = [];

  for (const refLine of refLines) {
    if (!refLine.trim()) {
      out.push("");
      continue;
    }
    const row = layout[layoutIdx];
    layoutIdx += 1;

    if (row?.kind === "heading") {
      const candidate = contentQueue[qi] ?? "";
      const candTrim = candidate.trim();
      if (
        candTrim &&
        !hasLeadingIndent(candidate) &&
        (isPlainTitleLine(candTrim) || parseAtxHeadingLine(candTrim))
      ) {
        out.push(contentQueue[qi] ?? "");
        qi += 1;
      } else {
        out.push(refLine);
      }
      continue;
    }

    let line = contentQueue[qi] ?? "";
    qi += 1;
    const refIndent = refLine.match(/^([\u3000]{1,2}| {2,})/)?.[0] ?? "";
    if (refIndent && line.trim() && !hasLeadingIndent(line)) {
      line = refIndent + line.replace(/^[\u3000 ]+/, "");
    }
    out.push(line);
  }
  while (qi < contentQueue.length) {
    out.push(contentQueue[qi] ?? "");
    qi += 1;
  }
  return out.join("\n");
}

export function highlightRangesForBody(
  localRanges: { start: number; end: number; reason?: string; segmentIndex?: number }[],
  prefixLen: number,
  bodyLen: number,
) {
  if (prefixLen <= 0) return localRanges;
  const out: typeof localRanges = [];
  for (const r of localRanges) {
    if (r.end <= prefixLen) continue;
    const start = Math.max(0, r.start - prefixLen);
    const end = Math.min(bodyLen, r.end - prefixLen);
    if (end <= start) continue;
    out.push({ ...r, start, end });
  }
  return out;
}

/** @deprecated 保留供旧引用；新代码请用 splitEssayLayoutLines */
export function splitEssayMarkdownBlocks(content: string) {
  return splitEssayLayoutLines(content).filter((l) => l.kind !== "empty");
}
