import { Button, Card, Col, Input, List, Row, Space, Tag, Typography, message } from "antd";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import GradingJobPanel from "../components/GradingJobPanel";
import { useEntitlement } from "../hooks/useEntitlement";

type Q = {
  id: string;
  title: string;
  question_type: string;
  question_type_label?: string;
  score: number;
  word_limit: number;
  word_min?: number;
};

type QDetail = Q & {
  prompt: string;
  reference_material?: string | null;
  scoring_points: { id: string; label: string; max_score: number }[];
};

export default function GradingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeJobId = searchParams.get("job");

  const { data: ent } = useEntitlement();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");

  const { data: list } = useQuery({
    queryKey: ["questions"],
    queryFn: () => api<Q[]>("/questions"),
  });

  const { data: detail } = useQuery({
    queryKey: ["question", selectedId],
    enabled: !!selectedId,
    queryFn: () => api<QDetail>(`/questions/${selectedId}`),
  });

  const questionFromUrl = searchParams.get("question");

  useEffect(() => {
    if (questionFromUrl && list?.some((q) => q.id === questionFromUrl)) {
      setSelectedId(questionFromUrl);
      return;
    }
    if (list?.length && !selectedId) setSelectedId(list[0].id);
  }, [list, selectedId, questionFromUrl]);

  const submit = useMutation({
    mutationFn: async () => {
      if (!selectedId) throw new Error("请选择作文题");
      const sub = await api<{ id: string }>("/submissions", {
        method: "POST",
        body: JSON.stringify({ question_id: selectedId, content: answer, status: "draft" }),
      });
      return api<{ grading_job_id: string }>(`/submissions/${sub.id}/grade`, { method: "POST" });
    },
    onSuccess: (res) => {
      message.success("已提交大作文批改，请在本页顶部查看进度");
      setSearchParams({ job: res.grading_job_id });
    },
    onError: (e) => message.error(String(e)),
  });

  const clearJob = () => {
    setSearchParams({});
  };

  const wordCount = answer.length;
  const wordMin = detail?.word_min ?? 800;
  const wordMax = detail?.word_limit ?? 1200;

  return (
    <>
      {activeJobId ? <GradingJobPanel jobId={activeJobId} onClose={clearJob} /> : null}

      <Row gutter={16}>
        <Col span={6}>
          <Card title="作文题库" size="small">
            <List
              dataSource={list ?? []}
              renderItem={(item) => (
                <List.Item
                  style={{ cursor: "pointer", background: item.id === selectedId ? "#e6f4ff" : undefined }}
                  onClick={() => setSelectedId(item.id)}
                >
                  <div>
                    <Typography.Text>{item.title}</Typography.Text>
                    <br />
                    <Tag style={{ marginTop: 4 }}>{item.question_type_label ?? "申论大作文"}</Tag>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={10}>
          <Card
            title="题干与作答要求"
            size="small"
            extra={
              detail ? (
                <Typography.Text type="secondary">
                  满分 {detail.score} · {wordMin}～{wordMax} 字
                </Typography.Text>
              ) : null
            }
          >
            <Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>{detail?.prompt}</Typography.Paragraph>
            {detail?.reference_material ? (
              <>
                <Typography.Title level={5} style={{ marginTop: 16 }}>
                  参考背景（可选阅读）
                </Typography.Title>
                <Typography.Paragraph type="secondary" style={{ whiteSpace: "pre-wrap" }}>
                  {detail.reference_material}
                </Typography.Paragraph>
              </>
            ) : null}
            {detail?.scoring_points?.length ? (
              <>
                <Typography.Title level={5} style={{ marginTop: 16 }}>
                  评分维度
                </Typography.Title>
                <Space wrap>
                  {detail.scoring_points.map((d) => (
                    <Tag key={d.id}>
                      {d.label}（{d.max_score} 分）
                    </Tag>
                  ))}
                </Space>
              </>
            ) : null}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="我的作文" size="small">
            <Input.TextArea
              rows={18}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="请在此输入完整大作文正文（含标题与分段）…"
            />
            <Typography.Text type={wordCount < wordMin ? "warning" : "secondary"}>
              {wordCount} 字（建议 {wordMin}～{wordMax} 字）
            </Typography.Text>
            <Button
              type="primary"
              block
              style={{ marginTop: 12 }}
              disabled={!ent?.licensed || !ent?.has_primary_ai_key}
              loading={submit.isPending}
              onClick={() => submit.mutate()}
            >
              提交批改
            </Button>
          </Card>
        </Col>
      </Row>
    </>
  );
}
