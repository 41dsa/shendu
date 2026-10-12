import { Alert, Button, Card, List, Result, Space, Spin, Steps, Typography } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export type GradingJobSubmissionSnapshot = {
  submission_id: string;
  question_id: string;
  is_custom: boolean;
  user_prompt: string | null;
  user_material: string | null;
  content: string;
};

export type GradingJob = {
  id: string;
  status: string;
  current_step: string | null;
  steps: { step: string; detail: string; at?: string }[];
  error_message: string | null;
  report_id: string | null;
  created_at?: string | null;
  submission?: GradingJobSubmissionSnapshot | null;
};

const GRADING_STEP_ORDER_BASE = [
  "parse_prompt",
  "check_requirements",
  "analyze_structure",
  "analyze_thesis",
  "analyze_argumentation",
  "rule_score",
  "llm_score",
  "review",
  "generate_report",
] as const;

const STEP_LABELS: Record<string, string> = {
  custom_standard: "解析题目与评分标准",
  parse_prompt: "解析题干",
  check_requirements: "核对字数与要求",
  analyze_structure: "分析篇章结构",
  analyze_thesis: "分析立意与观点",
  analyze_argumentation: "分析论证与素材",
  rule_score: "规则预评",
  llm_score: "AI 综合评分",
  review: "共识复核",
  generate_report: "生成报告",
  done: "完成",
  queued: "排队中",
};

const STEP_DETAIL_ZH: Record<string, string> = {
  done: "已完成",
  generating: "执行中",
  calling: "模型调用中",
  calling_llm: "模型调用中",
  cache_hit: "命中缓存",
  short_circuit: "提前结束",
  consensus: "共识复核",
  gate_reject: "未通过输入校验，已终止",
  level_adapter: "已匹配考试层级与字数要求",
  deterministic: "规则引擎匹配要点",
  scored: "规则打分完成",
  passed: "校验通过",
};

const EXAM_LEVEL_ZH: Record<string, string> = {
  provincial: "副省级",
  municipal: "市地级",
  enforcement: "行政执法",
};

const TIER_ZH: Record<string, string> = {
  t1: "一类文",
  t2: "二类文",
  t3: "三类文",
  t4: "四类文",
};

function formatStepDetail(detail: string): string {
  const mapped = STEP_DETAIL_ZH[detail];
  if (mapped) return mapped;
  if (detail.startsWith("gate_ok:")) {
    const level = detail.slice("gate_ok:".length);
    const levelZh = EXAM_LEVEL_ZH[level] ?? level;
    return `校验通过，考试层级：${levelZh}`;
  }
  if (detail.startsWith("hits:")) {
    const n = detail.slice("hits:".length);
    return `命中 ${n} 个要点`;
  }
  if (detail.startsWith("failed:")) {
    return `失败（${detail.slice("failed:".length)}）`;
  }
  if (EXAM_LEVEL_ZH[detail]) {
    return `考试层级：${EXAM_LEVEL_ZH[detail]}`;
  }
  if (TIER_ZH[detail]) {
    return `预估档位：${TIER_ZH[detail]}`;
  }
  return detail;
}

type Props = {
  jobId: string;
  onClose?: () => void;
};

function waitStartMs(data: GradingJob): number | null {
  const steps = data.steps ?? [];
  const cur = data.current_step;
  if (cur) {
    for (let i = steps.length - 1; i >= 0; i -= 1) {
      const s = steps[i];
      if (s.step === cur && s.at) {
        return new Date(s.at).getTime();
      }
    }
  }
  const last = steps.at(-1);
  if (last?.at) return new Date(last.at).getTime();
  if (data.created_at) return new Date(data.created_at).getTime();
  return null;
}

function formatWaitDuration(totalSec: number): string {
  const sec = Math.max(0, totalSec);
  if (sec < 60) return `${sec} 秒`;
  if (sec < 3600) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return s > 0 ? `${m} 分 ${s} 秒` : `${m} 分`;
  }
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return m > 0 ? `${h} 小时 ${m} 分` : `${h} 小时`;
}

function stepStatus(
  step: string,
  steps: { step: string; detail: string }[],
  current: string | null,
  inProgress: boolean,
): "finish" | "process" | "wait" | "error" {
  const entries = steps.filter((s) => s.step === step);
  if (entries.some((e) => e.detail === "done")) return "finish";
  if (inProgress && current === step) return "process";
  if (entries.length > 0 && inProgress) return "process";
  return "wait";
}

function gradingStepOrder(isCustom: boolean): readonly string[] {
  if (isCustom) return ["custom_standard", ...GRADING_STEP_ORDER_BASE];
  return GRADING_STEP_ORDER_BASE;
}

/** 批改页内常驻进度区（不自动跳转报告，避免一闪而过） */
export default function GradingJobPanel({ jobId, onClose }: Props) {
  const qc = useQueryClient();
  const [elapsedSec, setElapsedSec] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["grading-job", jobId],
    queryFn: () => api<GradingJob>(`/grading-jobs/${jobId}`),
    refetchInterval: (q) => {
      const st = q.state.data?.status;
      if (st === "failed") {
        qc.invalidateQueries({ queryKey: ["grading-queue"] });
        return false;
      }
      if (st === "succeeded") {
        if (q.state.data?.report_id) {
          qc.invalidateQueries({ queryKey: ["grading-queue"] });
          return false;
        }
        return 800;
      }
      return 1500;
    },
  });

  const waitStartKey = useMemo(() => {
    if (!data) return "";
    const ms = waitStartMs(data);
    return ms != null ? String(ms) : "";
  }, [data]);

  useEffect(() => {
    if (!waitStartKey) return;
    const start = Number(waitStartKey);
    const tick = () => setElapsedSec(Math.max(0, Math.floor((Date.now() - start) / 1000)));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [waitStartKey, data?.status]);

  const stepItems = useMemo(() => {
    if (!data) return [];
    const steps = data.steps ?? [];
    const current = data.current_step ?? steps.at(-1)?.step ?? null;
    const inProgress = data.status === "queued" || data.status === "running";
    const order = gradingStepOrder(Boolean(data.submission?.is_custom));
    return order.map((step) => ({
      title: STEP_LABELS[step] ?? step,
      status: stepStatus(step, steps, current, inProgress),
      description:
        inProgress && current === step && step === "custom_standard"
          ? "正在依据题干与材料，生成本题大作文的评分维度与要点，一般约 1～2 分钟；题干或材料较长时可能稍久。"
          : inProgress && current === step && step === "llm_score"
            ? "调用模型中…（通常 10～120 秒）"
            : undefined,
    }));
  }, [data]);

  if (isLoading || !data) {
    return (
      <Card title="大作文批改进度" style={{ marginBottom: 16 }}>
        <Spin tip="加载批改任务…" />
      </Card>
    );
  }

  const inProgress = data.status === "queued" || data.status === "running";

  if (data.status === "failed") {
    const raw = data.error_message ?? "";
    const subTitle =
      raw.includes("unexpected keyword argument")
        ? "自备题准备打分标准时程序接口不匹配（已修复需重启 API）。请重启后端服务后刷新页面再试一次。"
        : raw.includes("TIMEOUT") || raw.includes("超时")
        ? "模型调用超时或长时间无响应。请到「AI 设置」检查 OpenAI 兼容 Base URL（一般为 …/v1）、模型名与 Key，并点「测试连接」。开发环境需重启 API 后重试（已默认进程内批改，无需 Celery worker）。"
        : raw.includes("UPSTREAM") && raw.includes("400")
          ? "模型接口返回 400：常见原因是 Base URL 未带 /v1、模型名称错误或 Key 无权限。请到「AI 设置」核对并重新「测试连接」。"
          : raw.includes("INVALID_KEY") || raw.includes("NO_KEY")
            ? "API Key 未配置或无效，请在「AI 设置」保存 Key 并测试连接。"
            : raw || "请检查 API Key 与网络后重试";
    return (
      <Card
        title="大作文批改进度"
        style={{ marginBottom: 16 }}
        extra={onClose ? <Button type="link" onClick={onClose}>关闭</Button> : null}
      >
        <Result
          status="error"
          title="批改失败"
          subTitle={subTitle}
          extra={
            <Space>
              {onClose ? (
                <Button onClick={onClose}>关闭进度</Button>
              ) : null}
              <Button type="primary">
                <Link to="/settings/ai">打开 AI 设置</Link>
              </Button>
            </Space>
          }
        />
        {raw && raw !== subTitle ? (
          <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
            详情：{raw}
          </Typography.Paragraph>
        ) : null}
      </Card>
    );
  }

  if (data.status === "succeeded" && !data.report_id) {
    return (
      <Card title="大作文批改进度" style={{ marginBottom: 16, borderColor: "#b7eb8f" }}>
        <Spin tip="批改已完成，正在同步报告…" />
      </Card>
    );
  }

  if (data.status === "succeeded" && data.report_id) {
    return (
      <Card
        title="大作文批改进度"
        style={{ marginBottom: 16, borderColor: "#b7eb8f" }}
        extra={onClose ? <Button type="link" onClick={onClose}>关闭</Button> : null}
      >
        <Result
          status="success"
          title="批改完成"
          subTitle="点击下方按钮查看报告；也可在侧栏「批改报告」中随时打开。"
          extra={
            <Button type="primary" size="large">
              <Link to={`/reports/${data.report_id}`}>查看批改报告</Link>
            </Button>
          }
        />
      </Card>
    );
  }

  return (
    <Card
      title="大作文批改进度"
      style={{ marginBottom: 16, borderColor: "#91caff" }}
      extra={
        <Typography.Text type="secondary">
          {inProgress
            ? `本步已等待 ${formatWaitDuration(elapsedSec)}`
            : data.status === "queued"
              ? "排队中"
              : data.status === "running"
                ? "批改中"
                : data.status === "succeeded"
                  ? "已完成"
                  : data.status === "failed"
                    ? "失败"
                    : data.status}
          {onClose ? (
            <>
              {" · "}
              <Button type="link" size="small" onClick={onClose}>
                关闭
              </Button>
            </>
          ) : null}
        </Typography.Text>
      }
    >
      {inProgress && elapsedSec > 90 && data.current_step === "llm_score" && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="模型响应较慢"
          description={
            elapsedSec > 150
              ? "已超过 2 分钟，任务将自动判为失败并释放队列位；请关闭本区后检查 AI 设置并重新提交。"
              : "若超过 2 分钟仍无结果，请检查 AI 设置；刷新后会自动释放超时任务。"
          }
        />
      )}
      <Alert
        type="info"
        showIcon
        message="进度区会固定显示在本页顶部"
        description="大作文批改约 10～120 秒；完成后会出现「查看批改报告」按钮。"
        style={{ marginBottom: 16 }}
      />
      <Steps direction="vertical" size="small" items={stepItems} />
      {(data.steps?.length ?? 0) > 0 && (
        <List
          style={{ marginTop: 16 }}
          size="small"
          header="详细日志"
          dataSource={data.steps}
          renderItem={(s) => (
            <List.Item>
              {STEP_LABELS[s.step] ?? s.step} — {formatStepDetail(s.detail)}
              {s.at ? ` · ${new Date(s.at).toLocaleTimeString()}` : ""}
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
