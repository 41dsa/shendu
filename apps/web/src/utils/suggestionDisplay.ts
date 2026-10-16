type SuggestionObj = Record<string, unknown>;

function formatSuggestionDict(row: SuggestionObj): string {
  const content = String(row.内容 ?? row.content ?? row.text ?? row.建议 ?? row.suggestion ?? "").trim();
  const reason = String(row.原因 ?? row.reason ?? "").trim();
  if (content && reason) return `${content}（${reason}）`;
  return content || reason;
}

function tryParseLooseDict(text: string): SuggestionObj | null {
  const s = text.trim();
  if (!s.startsWith("{")) return null;
  try {
    const obj = JSON.parse(s) as unknown;
    return obj && typeof obj === "object" && !Array.isArray(obj) ? (obj as SuggestionObj) : null;
  } catch {
    /* Python repr 等 */
  }
  const normalized = s.replace(/'/g, '"').replace(/None/g, "null");
  try {
    const obj = JSON.parse(normalized) as unknown;
    return obj && typeof obj === "object" && !Array.isArray(obj) ? (obj as SuggestionObj) : null;
  } catch {
    return null;
  }
}

/** AI 建议列表项：对象 / dict 字符串 → 可读一句 */
export function formatSuggestionLine(raw: unknown): string {
  if (raw == null) return "";
  if (typeof raw === "object" && !Array.isArray(raw)) {
    return formatSuggestionDict(raw as SuggestionObj);
  }
  if (typeof raw === "string") {
    const s = raw.trim();
    if (!s) return "";
    if (s.startsWith("{") && (s.includes("内容") || s.includes("content"))) {
      const parsed = tryParseLooseDict(s);
      if (parsed) {
        const line = formatSuggestionDict(parsed);
        if (line) return line;
      }
    }
    return s;
  }
  return String(raw).trim();
}

export function normalizeSuggestionsList(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(formatSuggestionLine).filter((t) => t.length > 0).slice(0, 8);
}
