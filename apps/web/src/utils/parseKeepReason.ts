export type ParsedKeepReason = {
  /** 括号前导语 */
  prefix: string;
  /** 括号内：存在的问题 / 待改进点 */
  problem: string | null;
  /** 括号后、继续保持前：解决方案 */
  solution: string | null;
  /** 末尾鼓励语，如「继续保持。」 */
  encourage: string | null;
  /** 无法解析时整段原文 */
  fallback: string | null;
};

/** 解析「继续保持」说明：全角（）内为问题，其后为方案，末尾常为「继续保持」 */
export function parseKeepReason(reason: string): ParsedKeepReason {
  const trimmed = reason.trim();
  if (!trimmed) {
    return { prefix: "", problem: null, solution: null, encourage: null, fallback: null };
  }

  const match = trimmed.match(/^(.+?)（([^）]+)）([\s\S]+)$/);
  if (!match) {
    return { prefix: "", problem: null, solution: null, encourage: null, fallback: trimmed };
  }

  const prefix = match[1].trim();
  const problem = match[2].trim();
  let tail = match[3].trim();

  let encourage: string | null = null;
  const encourageMatch = tail.match(/^(.*?)(继续保持[。．]*\s*)$/);
  if (encourageMatch) {
    tail = encourageMatch[1].trim();
    encourage = encourageMatch[2].trim();
  }

  tail = tail.replace(/^[。．、；;\s]+|[。．、；;\s]+$/g, "").trim();
  const solution = tail.length > 0 ? tail : null;

  return {
    prefix,
    problem,
    solution,
    encourage: encourage ?? "继续保持。",
    fallback: null,
  };
}
