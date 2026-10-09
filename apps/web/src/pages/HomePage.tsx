import { Alert, Button, Card, Col, List, Progress, Row, Space, Spin, Statistic, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useEntitlement } from "../hooks/useEntitlement";

type ReportItem = {
  id: string;
  created_at: string;
  total_score: number | null;
  confidence: string | null;
  grading_job_id: string;
};

type ExamProfile = {
  exam_type: string;
  province: string;
  year: number;
  job_category: string;
};

type QuestionItem = {
  id: string;
  title: string;
  question_type_label?: string;
  score: number;
  word_min?: number;
  word_limit: number;
};

type ScoringPoint = { label?: string; earned?: number; max?: number };
type Issue = { tag?: string; explanation?: string };

const CONF_ZH: Record<string, string> = { high: "高", medium: "中", low: "低" };

const DEFAULT_FOCUS = [
  { tag: "W02 结构不完整", tip: "大作文建议「标题 + 开头 + 3 段分论点 + 结尾」，提交前自检分段。" },
  { tag: "W03 论证空洞", tip: "每个分论点至少 1 个事例或政策论据，避免只堆口号。" },
];

function dimensionProgress(points: ScoringPoint[] | undefined) {
  const labels = ["立意与观点", "结构与层次", "论证与素材", "语言表达"];
  return labels.map((label) => {
    const hit = points?.find((p) => p.label?.includes(label.slice(0, 2)) || p.label === label);
    const max = hit?.max ?? 10;
    const earned = hit?.earned ?? 0;
    const pct = max > 0 ? Math.round((earned / max) * 100) : 0;
    return { label, pct, earned, max };
  });
}

export default function HomePage() {
  const { data: ent, isLoading: entLoading } = useEntitlement();

  const { data: exam } = useQuery({
    queryKey: ["exam-profile"],
    queryFn: () => api<ExamProfile | null>("/exam-profiles"),
  });

  const { data: questions } = useQuery({
    queryKey: ["questions"],
    queryFn: () => api<QuestionItem[]>("/questions"),
  });

  const licensed = !!ent?.licensed;
  const ready = licensed && !!ent?.has_primary_ai_key;

  const { data: coachHome } = useQuery({
    queryKey: ["coach-home"],
    queryFn: () =>
      api<{
        focus_issue?: { label: string; count: number };
        today_training?: { title: string; reason: string; progress_done: number; progress_target: number };
        abilities?: { overall: number | null; dimensions: { name: string; score: number | null }[] };
        recent_reports?: ReportItem[];
      }>("/coach/home"),
    enabled: licensed,
  });

  const { data: reports } = useQuery({
    queryKey: ["reports"],
    queryFn: () => api<ReportItem[]>("/reports"),
    enabled: licensed,
  });

  const latestReportId = reports?.[0]?.id;
  const { data: latestDetail } = useQuery({
    queryKey: ["report", latestReportId],
    enabled: !!latestReportId,
    queryFn: () => api<{ payload: Record<string, unknown> }>(`/reports/${latestReportId}`),
  });

  if (entLoading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
        <Spin size="large" tip="加载中…" />
      </div>
    );
  }

  const payload = latestDetail?.payload ?? {};
  const dims = dimensionProgress(payload.scoring_points as ScoringPoint[] | undefined);
  const issues = (payload.issues as Issue[] | undefined)?.slice(0, 2) ?? [];
  const featured = questions?.[0];
  const recent = coachHome?.recent_reports ?? reports?.slice(0, 3) ?? [];
  const focusFromCoach = coachHome?.focus_issue;
  const training = coachHome?.today_training;

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card style={{ background: "linear-gradient(135deg,#e6f4ff,#ffffff)" }}>
        <Row align="middle" gutter={24}>
          <Col flex="auto">
            <Typography.Title level={3} style={{ marginTop: 0, marginBottom: 8 }}>
              申论大作文 · AI 批改
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              专注完整议论文的立意、结构、论证与语言表达；不是小题「读材料概括 / 分析 / 对策」练习。
            </Typography.Paragraph>
          </Col>
          <Col>
            {ready ? (
              <Button type="primary" size="large">
                <Link to={featured ? `/grading?question=${featured.id}` : "/grading"}>写一篇大作文</Link>
              </Button>
            ) : licensed ? (
              <Button type="primary" size="large">
                <Link to="/settings/ai">先配置 AI Key</Link>
              </Button>
            ) : (
              <Button type="primary" size="large">
                <Link to="/activate">激活后开始</Link>
              </Button>
            )}
          </Col>
        </Row>
      </Card>

      {!ent?.licensed && (
        <Alert
          type="warning"
          message="尚未激活"
          description="买断后兑换激活码，即可使用大作文批改（AI 算力需自备 API Key）。"
          action={
            <Button size="small" type="primary">
              <Link to="/activate">去激活</Link>
            </Button>
          }
          showIcon
        />
      )}
      {ent?.licensed && !ent.has_primary_ai_key && (
        <Alert
          type="info"
          message="请配置 AI Key"
          description="大作文批改将使用你在设置中填写的主模型 Key。"
          action={
            <Button size="small">
              <Link to="/settings/ai">AI 设置</Link>
            </Button>
          }
          showIcon
        />
      )}

      {training && licensed && (
        <Card title="今日训练（推荐）" extra={<Tag>{training.progress_done}/{training.progress_target}</Tag>}>
          <Typography.Text strong>{training.title}</Typography.Text>
          <Typography.Paragraph type="secondary">{training.reason}</Typography.Paragraph>
          <Space>
            <Button type="primary">
              <Link to="/training">去训练</Link>
            </Button>
            <Button>
              <Link to="/grading">去批改</Link>
            </Button>
          </Space>
        </Card>
      )}

      <Row gutter={16}>
        <Col xs={24} md={8}>
          <Card title="考试目标">
            {exam ? (
              <Space direction="vertical" size={4}>
                <Typography.Text>
                  {exam.exam_type} · {exam.province} · {exam.year}
                </Typography.Text>
                <Typography.Text type="secondary">{exam.job_category}</Typography.Text>
                <Button type="link" style={{ padding: 0 }}>
                  <Link to="/settings/exam">修改</Link>
                </Button>
              </Space>
            ) : (
              <>
                <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
                  设置国考/省考目标，便于后续推荐真题（P5）。
                </Typography.Paragraph>
                <Button>
                  <Link to="/settings/exam">去设置</Link>
                </Button>
              </>
            )}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="练习概览">
            <Row gutter={16}>
              <Col span={12}>
                <Statistic title="已批改篇数" value={reports?.length ?? 0} suffix="篇" />
              </Col>
              <Col span={12}>
                <Statistic
                  title="最近得分"
                  value={reports?.[0]?.total_score ?? "—"}
                  suffix={reports?.[0]?.total_score != null ? "分" : undefined}
                />
              </Col>
            </Row>
            {reports?.[0]?.confidence && (
              <Tag style={{ marginTop: 12 }} color="blue">
                最近置信度 {CONF_ZH[reports[0].confidence!] ?? reports[0].confidence}
              </Tag>
            )}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="推荐题目">
            {featured ? (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Typography.Text strong>{featured.title}</Typography.Text>
                <Tag>{featured.question_type_label ?? "申论大作文"}</Tag>
                <Typography.Text type="secondary">
                  满分 {featured.score} · {featured.word_min ?? 800}～{featured.word_limit} 字
                </Typography.Text>
                {ready ? (
                  <Button type="primary" block>
                    <Link to={`/grading?question=${featured.id}`}>去写这篇</Link>
                  </Button>
                ) : (
                  <Typography.Text type="secondary">激活并配置 Key 后可练习</Typography.Text>
                )}
              </Space>
            ) : (
              <Typography.Text type="secondary">暂无题目，请运行 init_db 导入示例大作文。</Typography.Text>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="大作文能力（最近一次）">
            {!latestReportId ? (
              <Typography.Text type="secondary">完成首次批改后，这里会展示四维度得分比例。</Typography.Text>
            ) : (
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                {dims.map((d) => (
                  <div key={d.label}>
                    <Typography.Text>{d.label}</Typography.Text>
                    <Progress percent={d.pct} format={() => `${d.earned}/${d.max}`} />
                  </div>
                ))}
              </Space>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title="待加强（大作文）"
            extra={
              ready ? (
                <Button type="link">
                  <Link to="/grading">再练一篇</Link>
                </Button>
              ) : null
            }
          >
            <List
              size="small"
              dataSource={
                focusFromCoach
                  ? [{ tag: focusFromCoach.label, tip: `近 ${focusFromCoach.count} 次批改出现，建议优先修改后二次作答。` }]
                  : issues.length
                    ? issues.map((i) => ({
                        tag: i.tag ?? "问题",
                        tip: i.explanation ?? "见最近报告详情",
                      }))
                    : DEFAULT_FOCUS
              }
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta title={<Tag color="orange">{item.tag}</Tag>} description={item.tip} />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="最近批改"
        extra={
          <Button type="link">
            <Link to="/reports">全部报告</Link>
          </Button>
        }
      >
        {!licensed ? (
          <Typography.Text type="secondary">激活后可查看历史大作文批改报告。</Typography.Text>
        ) : !recent.length ? (
          <Typography.Text type="secondary">还没有报告，从「写一篇大作文」开始。</Typography.Text>
        ) : (
          <List
            dataSource={recent}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button key="go" type="link">
                    <Link to={`/reports/${item.id}`}>查看</Link>
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <>
                      {item.total_score != null ? `${item.total_score} 分` : "批改报告"}{" "}
                      {item.confidence && (
                        <Tag>{CONF_ZH[item.confidence] ?? item.confidence}置信</Tag>
                      )}
                    </>
                  }
                  description={new Date(item.created_at).toLocaleString()}
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </Space>
  );
}
