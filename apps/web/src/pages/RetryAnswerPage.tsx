import { Alert, Button, Card, Input, List, Space, Tag, Typography, message } from "antd";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";

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
};

export default function RetryAnswerPage() {
  const { reportId } = useParams();
  const navigate = useNavigate();
  const [answer, setAnswer] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["retry-context", reportId],
    enabled: !!reportId,
    queryFn: () => api<RetryContext>(`/coach/reports/${reportId}/retry-context`),
  });

  const submit = useMutation({
    mutationFn: () =>
      api<{ grading_job_id: string }>(`/coach/reports/${reportId}/retry`, {
        method: "POST",
        body: JSON.stringify({ content: answer }),
      }),
    onSuccess: (res) => {
      message.success("已提交第二次批改");
      navigate(`/grading?job=${res.grading_job_id}`);
    },
    onError: (e) => message.error(String(e)),
  });

  if (isLoading || !data) {
    return <Card loading={isLoading}>加载中…</Card>;
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title={`二次作答 · ${data.question_title}`} extra={<Tag>第 {data.attempt_next} 稿</Tag>}>
        <Alert
          type="info"
          showIcon
          message={`首次得分 ${data.first_score ?? "—"}，请针对下列问题修改后重写全文`}
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

      <Card title="首次主要问题">
        <List
          size="small"
          dataSource={data.issues}
          locale={{ emptyText: "暂无结构化问题，请参考下方建议" }}
          renderItem={(item) => (
            <List.Item>
              <Tag color="orange">{item.tag}</Tag> {item.explanation}
            </List.Item>
          )}
        />
        {data.suggestions.length > 0 && (
          <>
            <Typography.Title level={5} style={{ marginTop: 16 }}>
              AI 建议
            </Typography.Title>
            <List size="small" dataSource={data.suggestions} renderItem={(s, i) => <List.Item>{i + 1}. {s}</List.Item>} />
          </>
        )}
      </Card>

      <Card title="第一次原文（只读）">
        <Typography.Paragraph style={{ whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto" }}>
          {data.first_content}
        </Typography.Paragraph>
      </Card>

      <Card title="第二次作文">
        <Input.TextArea rows={16} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="在此撰写修改后的完整大作文…" />
        <Space style={{ marginTop: 16 }}>
          <Button type="primary" loading={submit.isPending} onClick={() => submit.mutate()} disabled={answer.trim().length < 10}>
            提交批改
          </Button>
          <Button>
            <Link to={`/reports/${reportId}`}>返回报告</Link>
          </Button>
        </Space>
      </Card>
    </Space>
  );
}
