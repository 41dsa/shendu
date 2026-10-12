/** Markdown 范文：空行分段，段首缩进（全角或 CSS 2em） */

export type EssayMdBlock = {
  start: number;
  end: number;
  text: string;
  /** 行内已有全角/空格缩进，不再叠加 text-indent */
  hasCharIndent: boolean;
  isTitle: boolean;
};

function hasLeadingIndent(line: string): boolean {
  return /^([\u3000]{1,2}| {2,})/.test(line);
}

function isTitleLine(line: string): boolean {
  const t = line.trim();
  return t.length > 0 && t.length <= 48 && !/[。！？；]/.test(t);
}

export function splitEssayMarkdownBlocks(content: string): EssayMdBlock[] {
  const normalized = content.replace(/\r\n/g, "\n");
  if (!normalized.trim()) return [];

  const lines = normalized.split("\n");
  const blocks: EssayMdBlock[] = [];
  let cursor = 0;
  let buf: { line: string; start: number; end: number }[] = [];

  const flush = () => {
    if (!buf.length) return;
    const text = buf.map((b) => b.line).join("\n");
    const start = buf[0].start;
    const end = buf[buf.length - 1].end;
    const firstLine = buf[0].line;
    blocks.push({
      start,
      end,
      text,
      hasCharIndent: hasLeadingIndent(firstLine),
      isTitle: false,
    });
    buf = [];
  };

  for (const line of lines) {
    const start = cursor;
    const end = cursor + line.length;
    cursor = end + 1;

    if (!line.trim()) {
      flush();
      continue;
    }
    buf.push({ line, start, end });
  }
  flush();

  if (blocks.length > 0) {
    const first = blocks[0];
    first.isTitle =
      isTitleLine(first.text.split("\n")[0] ?? "") &&
      !first.hasCharIndent &&
      !/[。！？；]/.test(first.text.trim());
  }

  return blocks;
}
