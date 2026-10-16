/**
 * 申论正文字数：与 services/api/app/domain/essay.py count_shenlun_body_chars 一致。
 * 不计空格/换行、不计文首标题；正文其余字符均计（含中英文标点）。
 */

import { hasLeadingIndent, parseAtxHeadingLine } from "./essayMarkdownBlocks";

const SINGLE_GRID_PUNCT = new Set("，。；：？！、");
const DOUBLE_GRID_CHARS = new Set("《》（）\u201c\u201d\u2018\u2019");

function isTitleLineForShenlunCount(line: string): boolean {
  const t = line.trim();
  if (!t) return false;
  if (parseAtxHeadingLine(t)) return true;
  if (hasLeadingIndent(line)) return false;
  const han = (t.match(/[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g) ?? []).length;
  if (han === 0) return false;
  if (t.length > 22 || /[。！？；]/.test(t)) return false;
  if (/[，,]/.test(t)) return false;
  if (/[是在的有与为以这那]/.test(t)) return false;
  return han >= 2 && han <= 18;
}

export function essayBodyExcludingTitle(content: string): string {
  const lines = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
  let titleIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    if (isTitleLineForShenlunCount(line)) {
      titleIdx = i;
    }
    break;
  }
  if (titleIdx < 0) return content;
  return lines.filter((_, i) => i !== titleIdx).join("\n");
}

/** 正文汉字（不含标点） */
export function countShenlunBodyHanChars(text: string): number {
  const body = essayBodyExcludingTitle(text);
  const matches = body.match(/[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g);
  return matches ? matches.length : 0;
}

/** 申论正文字数：正文非空白字符（标点中英文均计） */
export function countShenlunBodyChars(text: string): number {
  const body = essayBodyExcludingTitle(text);
  let n = 0;
  for (const ch of body) {
    if (!/\s/u.test(ch)) n += 1;
  }
  return n;
}

/** @deprecated 方格纸计字；批改页与门槛请用 countShenlunBodyHanChars */
export function countEssayChars(text: string): number {
  if (!text) return 0;
  const s = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  let total = 0;
  let i = 0;
  while (i < s.length) {
    const ch = s[i];
    if (ch === " " || ch === "\t" || ch === "\n") {
      i += 1;
      continue;
    }
    if (s.startsWith("……", i)) {
      total += 2;
      i += 2;
      continue;
    }
    if (s.startsWith("——", i)) {
      total += 2;
      i += 2;
      continue;
    }
    if (ch === "…") {
      let j = i;
      while (j < s.length && s[j] === "…") j += 1;
      total += 2;
      i = j;
      continue;
    }
    if (ch === "—") {
      if (i + 1 < s.length && s[i + 1] === "—") {
        total += 2;
        i += 2;
      } else {
        total += 2;
        i += 1;
      }
      continue;
    }
    if (DOUBLE_GRID_CHARS.has(ch)) {
      total += 2;
      i += 1;
      continue;
    }
    if (SINGLE_GRID_PUNCT.has(ch) || ",.;:?!".includes(ch)) {
      total += 1;
      i += 1;
      continue;
    }
    total += 1;
    i += 1;
  }
  return total;
}
