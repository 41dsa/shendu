import { Alert, Button, Card, List, Result, Spin, Steps, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export type GradingJob = {
  id: string;
  status: string;
  current_step: string | null;
  steps: { step: string; detail: string }[];
  error_message: string | null;
  report_id: string | null;
};

const STEP_LABELS: Record<string, string> = {
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
  identify_type: "识别题型",
  analyze_requirement: "分析作答要求",
  structure_material: "整理参考材料",
  extract_points: "提取评分维度",
  analyze_answer: "分析作文",
  match_points: "维度对照",
};

type Props = {
  jobId: string;
  onClose?: () => void;
};

/** 批改页内常驻进度区（不自动跳转报告，避免一闪而过） */
export default function GradingJobPanel({ jobId, onClose }: Props) {
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["grading-job", jobId],
    queryFn: () => api<GradingJob>(`/grading-jobs/${jobId}`),
    refetchInterval: (q) => {
      const st = q.state.data?.status;
      if (st === "succeeded" || st === "failed") return false;
      return 1500;
    },
  });

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
      raw.includes("UPSTREAM") && raw.includes("400")
        ? "模型接口返回 400：常见原因是 Base URL 未带 /v1、模型名称错误或 Key 无权限。请到「AI 设置」核对 DeepSeek 为 https://api.deepseek.com/v1、模型 deepseek-chat，并重新「测试连接」后再批改。"
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
            <Button type="primary">
              <Link to="/settings/ai">打开 AI 设置</Link>
            </Button>
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

  const currentIndex = Math.max(0, (data.steps?.length ?? 1) - 1);

  return (
    <Card
      title="大作文批改进度"
      style={{ marginBottom: 16, borderColor: "#91caff" }}
      extra={
        <Typography.Text type="secondary">
          {inProgress ? (isFetching ? "刷新中…" : "进行中") : data.status}
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
      <Alert
        type="info"
        showIcon
        message="进度区会固定显示在本页顶部"
        description="大作文批改约 10～60 秒，请勿离开「批改」页；完成后此处会出现「查看批改报告」按钮。"
        style={{ marginBottom: 16 }}
      />
      <Steps
        direction="vertical"
        size="small"
        current={currentIndex}
        status={inProgress ? "process" : "wait"}
        items={(data.steps.length ? data.steps : [{ step: "queued", detail: "waiting" }]).map((s) => ({
          title: STEP_LABELS[s.step] ?? s.step,
          description: s.detail === "calling" ? "调用模型中…" : undefined,
        }))}
      />
      {data.steps.length > 0 && (
        <List
          style={{ marginTop: 16 }}
          size="small"
          header="详细日志"
          dataSource={data.steps}
          renderItem={(s) => (
            <List.Item>
              {s.step} — {s.detail}
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
