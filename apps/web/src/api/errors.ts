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
  message.error(error instanceof Error ? error.message : fallback);
}
