import { message } from "antd";

/** 与后端 detail 字段对齐的可识别错误码 */
export type ApiErrorCode =
  | "LICENSE_REQUIRED"
  | "AI_KEY_REQUIRED"
  | "GRADING_QUEUE_FULL"
  | "UNKNOWN";

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly httpStatus: number;

  constructor(code: ApiErrorCode, detail: string, httpStatus: number) {
    super(detail);
    this.name = "ApiError";
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

const CODE_PATTERN =
  /^(LICENSE_REQUIRED|AI_KEY_REQUIRED|GRADING_QUEUE_FULL)$/;

export function parseApiError(httpStatus: number, detail: string): ApiError {
  const trimmed = detail.trim();
  if (CODE_PATTERN.test(trimmed)) {
    return new ApiError(trimmed as ApiErrorCode, trimmed, httpStatus);
  }
  return new ApiError("UNKNOWN", trimmed || "请求失败", httpStatus);
}

export function getApiErrorCode(error: unknown): ApiErrorCode | null {
  if (error instanceof ApiError) return error.code;
  const text = String(error);
  for (const code of ["LICENSE_REQUIRED", "AI_KEY_REQUIRED", "GRADING_QUEUE_FULL"] as const) {
    if (text.includes(code)) return code;
  }
  return null;
}

function stripTechnicalNoise(text: string): string {
  return text
    .replace(/^ApiError:\s*/i, "")
    .replace(/\(request_id:\s*[a-f0-9-]+\)/gi, "")
    .replace(/^UPSTREAM:\s*/i, "")
    .replace(/模型调用失败\s*\(\d+\)\s*[:：]?\s*/gi, "")
    .trim();
}

const JOB_ERROR_HINTS: { test: (raw: string, body: string) => boolean; message: string }[] = [
  {
    test: (raw, body) => raw.includes("DUPLICATE_ANSWER") && body.includes("重作"),
    message: "重作正文与已批改过的内容完全相同，请修改后再提交。",
  },
  {
    test: (raw) => raw.includes("DUPLICATE_ANSWER"),
    message:
      "与同一「作答要求 + 给定材料 + 正文」的已批改记录完全一致。请修改作文正文后再提交，或在「批改报告」中查看上次结果。",
  },
  {
    test: (raw) =>
      /INSUFFICIENT_BALANCE|Insufficient Balance|402/.test(raw) ||
      /余额不足/.test(raw),
    message:
      "模型账户余额不足。请在模型服务商控制台充值或更换有余额的 API Key，并在「AI 设置」中更新后重试。",
  },
  {
    test: (raw) => /INVALID_KEY|NO_KEY|NO_CREDENTIAL|AI_KEY_REQUIRED/.test(raw),
    message: "未配置或无效的 API Key。请打开「AI 设置」填写 Key、Base URL 与模型名，并点击「测试连接」。",
  },
  {
    test: (raw) => /RATE_LIMIT|429/.test(raw),
    message: "请求过于频繁或账户受限，请稍后再试。",
  },
  {
    test: (raw) => /TIMEOUT|超时/.test(raw),
    message: "模型响应超时。请检查网络与「AI 设置」，稍后重试。",
  },
  {
    test: (raw) => /NETWORK/.test(raw),
    message: "无法连接模型服务，请检查网络与 Base URL。",
  },
  {
    test: (raw) => raw.includes("UPSTREAM") && raw.includes("400"),
    message:
      "模型接口参数有误。请检查「AI 设置」：Base URL 是否以 /v1 结尾、模型名是否与厂商文档一致。",
  },
  {
    test: (raw) => raw.includes("UPSTREAM"),
    message: "调用模型失败。请检查「AI 设置」中的 Key、Base URL、模型名与账户余额。",
  },
  {
    test: (raw) => raw.includes("unexpected keyword argument"),
    message: "服务版本不匹配。请重启后端 API 后刷新页面再试。",
  },
];

/**
 * 批改任务 error_message、接口 detail 等统一转为用户可读文案（不含技术码与 request_id）
 */
export function formatUserFacingError(raw: string, fallback = "操作失败，请稍后重试"): string {
  const cleaned = stripTechnicalNoise(raw);
  if (!cleaned) return fallback;

  const codeMatch = cleaned.match(/^([A-Z][A-Z0-9_]*):\s*(.+)$/s);
  const code = codeMatch?.[1] ?? "";
  const body = (codeMatch?.[2] ?? cleaned).trim();

  for (const row of JOB_ERROR_HINTS) {
    if (row.test(`${code}:${body}`, body)) return row.message;
  }

  if (body && !/^UPSTREAM/i.test(body) && !/request_id/i.test(body)) {
    return body;
  }

  return fallback;
}

/** 将 Error / ApiError 转为用户可读说明 */
export function formatApiErrorMessage(error: unknown, fallback = "操作失败"): string {
  if (error instanceof ApiError) {
    const license = getApiErrorCode(error);
    if (license === "LICENSE_REQUIRED") {
      return "账号尚未激活，请先到「购买/激活」兑换激活码。";
    }
    if (license === "AI_KEY_REQUIRED") {
      return "请先在「AI 设置」中配置主模型 API Key。";
    }
    if (license === "GRADING_QUEUE_FULL") {
      return "批改队列已满（最多 2 个进行中）。请等待当前任务完成后再提交。";
    }
  }
  const text = error instanceof Error ? error.message : String(error ?? "");
  return formatUserFacingError(text, fallback);
}

/** FE-702：统一引导，避免裸 Error 字符串 */
export function showApiError(error: unknown, fallback = "操作失败"): void {
  const code = getApiErrorCode(error);
  if (code === "LICENSE_REQUIRED") {
    message.warning("账号尚未激活，请先到「购买/激活」兑换激活码。");
    return;
  }
  if (code === "AI_KEY_REQUIRED") {
    message.warning("请先在「AI 设置」中配置主模型 API Key。");
    return;
  }
  if (code === "GRADING_QUEUE_FULL") {
    message.warning(
      "批改队列已满（最多 2 个进行中）。请打开顶部进度条等待完成；若卡住超过 5 分钟，请刷新后重试（系统会自动释放超时任务）。",
      6,
    );
    return;
  }
  const friendly = formatApiErrorMessage(error, fallback);
  if (/余额不足/.test(friendly)) {
    message.warning(friendly, 8);
    return;
  }
  message.error(friendly);
}
