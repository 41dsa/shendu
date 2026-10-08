import { Alert, Button, Card, Col, Collapse, List, Row, Space, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";

type ScoringPoint = {
  id?: string;
  label?: string;
  earned?: number;
  max?: number;
  hit?: string;
  reason?: string;
  material_ref?: string;
};

type Issue = {
  tag?: string;
  severity?: string;
  explanation?: string;
  user_quote?: string;
  material_ref?: string;
};

const HIT_COLOR: Record<string, string> = {
  full: "success",
  partial: "warning",
  miss: "error",
};

const HIT_LABEL: Record<string, string> = {
  full: "命中",
  partial: "部分命中",
  miss: "未命中",
};

const CONF_LABEL: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export default function ReportPage() {
  const { reportId } = useParams();
  const { data } = useQuery({
    queryKey: ["report", reportId],
    enabled: !!reportId,
    queryFn: () => api<{ id: string; payload: Record<string, unknown> }>(`/reports/${reportId}`),
  });
  const { data: basisData } = useQuery({
    queryKey: ["report-basis", reportId],
    enabled: !!reportId,
    queryFn: () => api<{ basis: Record<string, unknown> }>(`/reports/${reportId}/basis`),
  });

  const p = data?.payload ?? {};
  const confidence = String(p.confidence ?? "medium");
  const displayMode = p.display_mode === "reference_only";
  const maxScore = Number(p.max_score ?? 10);
  const range = (p.score_range as number[]) ?? [];
  const comparison = p.comparison as
    | {
        first_score?: number;
        second_score?: number;
        score_delta?: number;
        first_hit_rate?: number;
        second_hit_rate?: number;
        hit_rate_delta?: number;
        issue_changes?: { tag?: string; label?: string; status?: string }[];
      }
    | undefined;

  const ISSUE_STATUS: Record<string, string> = {
    improved: "已改善",
    resolved: "已解决",
    unchanged: "未变",
    worse: "加重",
    new: "新出现",
  };

  return (
    <Card
      title="批改报告"
      extra={
        <Button>
          <Link to="/reports">全部报告</Link>
        </Button>
      }
    >
      {displayMode && (
        <Alert
          type="warning"
          showIcon
          message="评分仅供参考"
          description={String(p.short_circuit_reason ?? "置信度较低，建议完善作答后重新提交。")}
          style={{ marginBottom: 16 }}
        />
      )}

      <Space wrap align="center">
        <Typography.Title level={2} style={{ margin: 0 }}>
          {displayMode ? "—" : String(p.total_score ?? "-")} / {maxScore}
        </Typography.Title>
        {range.length === 2 && (
          <Tag>合理区间 {range[0]}～{range[1]} 分</Tag>
        )}
        <Tag color={confidence === "high" ? "green" : confidence === "low" ? "red" : "blue"}>
          置信度 {CONF_LABEL[confidence] ?? confidence}
        </Tag>
        <Tag>共识一致率 {String(p.consensus_rate ?? "-")}%</Tag>
        {p.from_cache ? <Tag>缓存命中</Tag> : null}
        {p.attempt ? <Tag>第 {String(p.attempt)} 稿</Tag> : null}
      </Space>

      {comparison && (
        <Alert
          type="success"
          showIcon
          style={{ marginTop: 16 }}
          message="二次批改对比"
          description={
            <Space direction="vertical">
              <span>
                分数 {comparison.first_score} → {comparison.second_score}（
                {comparison.score_delta != null && comparison.score_delta >= 0 ? "+" : ""}
                {comparison.score_delta}）
              </span>
              <span>
                维度命中率 {comparison.first_hit_rate}% → {comparison.second_hit_rate}%（
                {comparison.hit_rate_delta != null && comparison.hit_rate_delta >= 0 ? "+" : ""}
                {comparison.hit_rate_delta}%）
              </span>
              {(comparison.issue_changes ?? []).length > 0 && (
                <List
                  size="small"
                  dataSource={comparison.issue_changes}
                  renderItem={(c) => (
                    <List.Item>
                      {c.label ?? c.tag} — {ISSUE_STATUS[c.status ?? ""] ?? c.status}
                    </List.Item>
                  )}
                />
              )}
            </Space>
          }
        />
      )}

      <div style={{ marginTop: 16 }}>
        <Collapse
          items={[
            {
              key: "basis",
              label: "查看评分依据",
              children: (
                <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 12 }}>
                  {JSON.stringify(basisData?.basis ?? p.scoring_basis ?? {}, null, 2)}
                </pre>
              ),
            },
          ]}
        />
      </div>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={14}>
          <Typography.Title level={5}>各维度得分</Typography.Title>
          <List
            grid={{ gutter: 8, column: 1 }}
            dataSource={(p.scoring_points as ScoringPoint[]) ?? []}
            renderItem={(item) => (
              <List.Item>
                <Card size="small" type="inner">
                  <Space direction="vertical" size={4}>
                    <Space>
                      <Tag color={HIT_COLOR[item.hit ?? ""] ?? "default"}>
                        {HIT_LABEL[item.hit ?? ""] ?? item.hit}
                      </Tag>
                      <Typography.Text strong>{item.label}</Typography.Text>
                      <Typography.Text>
                        {item.earned}/{item.max} 分
                      </Typography.Text>
                    </Space>
                    {item.reason && (
                      <Typography.Text type="secondary">{item.reason}</Typography.Text>
                    )}
                    {(item as { evidence_ref?: string; material_ref?: string }).evidence_ref ||
                    item.material_ref ? (
                      <Typography.Text type="secondary">
                        依据：
                        {(item as { evidence_ref?: string }).evidence_ref ?? item.material_ref}
                      </Typography.Text>
                    ) : null}
                  </Space>
                </Card>
              </List.Item>
            )}
          />
        </Col>
        <Col span={10}>
          <Typography.Title level={5}>主要问题</Typography.Title>
          <List
            dataSource={(p.issues as Issue[]) ?? []}
            locale={{ emptyText: "暂无结构化问题标签" }}
            renderItem={(item) => (
              <List.Item>
                <Space direction="vertical" size={4}>
                  <Space>
                    <Tag color="orange">{item.tag}</Tag>
                    {item.severity && <Tag>{item.severity}</Tag>}
                  </Space>
                  <Typography.Paragraph style={{ marginBottom: 0 }}>{item.explanation}</Typography.Paragraph>
                  {item.user_quote && (
                    <Typography.Text type="secondary">你的表述：「{item.user_quote}」</Typography.Text>
                  )}
                </Space>
              </List.Item>
            )}
          />
          <Typography.Title level={5} style={{ marginTop: 16 }}>
            AI 建议
          </Typography.Title>
          <List
            dataSource={(p.suggestions as string[]) ?? []}
            renderItem={(s, i) => (
              <List.Item>
                {i + 1}. {s}
              </List.Item>
            )}
          />
          <Button type="primary" block style={{ marginTop: 16 }}>
            <Link to={`/reports/${reportId}/retry`}>重新作答</Link>
          </Button>
        </Col>
      </Row>
    </Card>
  );
}
