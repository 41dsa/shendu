import { Alert, Button, Card, Input, List, Space, Tag, Typography, message } from "antd";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { api } from "../api/client";
import { issueAnalysisText, issueBadgeText } from "../utils/issueDisplay";
import { formatSuggestionLine } from "../utils/suggestionDisplay";
import { issueTypeTagStyle, severityLabel, severityVisual } from "../utils/severityLabel";

type RetryContext = {
  report_id: string;
  question_id: string;
  question_title: string;
  prompt: string;
  reference_material?: string | null;
  first_content: string;
  first_score: number | null;
  issues: { tag?: string; severity?: string; explanation?: string }[];
  suggestions: string[];
  attempt_next: number;
  retry_allowed?: boolean;
  retry_limit_message?: string | null;
  retry_max_count?: number;
  retry_used_count?: number;
  first_pass_tier_label?: string | null;
};

export default function RetryAnswerPage() {
  const { reportId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [answer, setAnswer] = useState("");

  useEffect(() => {
    setAnswer("");
  }, [reportId, location.key]);

  const { data, isLoading } = useQuery({
    queryKey: ["retry-context", reportId, location.key],
    enabled: !!reportId,
    refetchOnMount: "always",
    queryFn: () => api<RetryContext>(`/coach/reports/${reportId}/retry-context`),
  });

  const submit = useMutation({
    mutationFn: () =>
      api<{ grading_job_id: string }>(`/coach/reports/${reportId}/retry`, {
        method: "POST",
        body: JSON.stringify({ content: answer }),
      }),
    onSuccess: (res) => {
      message.success("已提交批改");
      navigate(`/grading?job=${res.grading_job_id}`);
    },
    onError: (e) => message.error(String(e)),
  });

  if (isLoading || !data) {
    return <Card loading={isLoading}>加载中…</Card>;
  }

  const retryAllowed = data.retry_allowed !== false;
  const retryMax = Math.max(1, Number(data.retry_max_count) || 1);
  const retryUsed = Math.max(0, Number(data.retry_used_count) || 0);
  const tierLabel = data.first_pass_tier_label?.trim() || "";

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title={`重新作答 · ${data.question_title}`} extra={<Tag>第 {data.attempt_next} 稿</Tag>}>
        <Alert
          type="info"
          showIcon
          message={`首稿得分 ${data.first_score ?? "—"}，请针对下列问题修改后重写全文`}
          description={
            tierLabel
              ? `首稿为${tierLabel}，最多可重新批改 ${retryMax} 次（已用 ${retryUsed} 次，本次为第 ${data.attempt_next} 稿）。`
              : `最多可重新批改 ${retryMax} 次（已用 ${retryUsed} 次）。`
          }
          style={{ marginBottom: 16 }}
        />
        <Typography.Title level={5}>题干</Typography.Title>
        <Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>{data.prompt}</Typography.Paragraph>
        {data.reference_material ? (
          <>
            <Typography.Title level={5} style={{ marginTop: 16 }}>
              给定材料
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ whiteSpace: "pre-wrap" }}>
              {data.reference_material}
            </Typography.Paragraph>
          </>
        ) : null}
      </Card>

      <Card title="待改进问题（基于当前报告）">
        <List
          size="small"
          dataSource={data.issues}
          locale={{ emptyText: "暂无结构化问题，请参考下方建议" }}
          renderItem={(item) => (
            <List.Item>
              <>
                <Tag style={issueTypeTagStyle}>{issueBadgeText(item)}</Tag>
                {item.severity ? (
                  <Tag style={severityVisual(item.severity).style}>{severityLabel(item.severity)}</Tag>
                ) : null}{" "}
                {issueAnalysisText(item)}
              </>
            </List.Item>
          )}
        />
        {data.suggestions.length > 0 && (
          <>
            <Typography.Title level={5} style={{ marginTop: 16 }}>
              AI 建议
            </Typography.Title>
            <List
              size="small"
              dataSource={data.suggestions}
              renderItem={(s, i) => <List.Item>{i + 1}. {formatSuggestionLine(s)}</List.Item>}
            />
          </>
        )}
      </Card>

      <Card title="首稿原文（只读）">
        <Typography.Paragraph style={{ whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto" }}>
          {data.first_content}
        </Typography.Paragraph>
      </Card>

      {!retryAllowed ? (
        <Alert
          type="warning"
          showIcon
          message="无法再次重新批改"
          description={data.retry_limit_message ?? "已达到本篇允许的重新批改次数上限。"}
        />
      ) : null}

      <Card title={`第 ${data.attempt_next} 稿作文`}>
        <Input.TextArea
          rows={16}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="在此撰写修改后的完整大作文…"
          disabled={!retryAllowed}
        />
        <Space style={{ marginTop: 16 }}>
          <Button
            type="primary"
            loading={submit.isPending}
            onClick={() => submit.mutate()}
            disabled={!retryAllowed || answer.trim().length < 10}
          >
            提交批改
          </Button>
          <Button onClick={() => navigate(`/reports/${reportId}`)}>返回报告</Button>
        </Space>
      </Card>
    </Space>
  );
}
