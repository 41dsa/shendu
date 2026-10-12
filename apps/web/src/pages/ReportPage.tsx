import { Alert, Button, Card, Col, Collapse, Input, List, Modal, Row, Space, Tag, Typography, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import ReportRewriteDemo from "../components/ReportRewriteDemo";
import ReportScoringBasis from "../components/ReportScoringBasis";
import { normalizeReportPayload, refreshComparisonScores } from "../utils/reportPayload";
import { issueAnalysisText, issueBadgeText } from "../utils/issueDisplay";
import { issueTypeTagStyle, severityLabel, severityVisual } from "../utils/severityLabel";

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
  low: "参考",
};

const CONF_TAG_COLOR: Record<string, string> = {
  high: "green",
  medium: "blue",
  low: "gold",
};

export default function ReportPage() {
  const { reportId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [disputeOpen, setDisputeOpen] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");
  const { data } = useQuery({
    queryKey: ["report", reportId],
    enabled: !!reportId,
    queryFn: () =>
      api<{
        id: string;
        payload: Record<string, unknown>;
        submission?: { content?: string; user_prompt?: string | null; user_material?: string | null };
      }>(`/reports/${reportId}`),
  });
  const submitDispute = useMutation({
    mutationFn: () =>
      api(`/reports/${reportId}/disputes`, {
        method: "POST",
        body: JSON.stringify({ reason: disputeReason }),
      }),
    onSuccess: () => {
      message.success("争议已提交");
      setDisputeOpen(false);
      qc.invalidateQueries({ queryKey: ["me-summary"] });
    },
    onError: (e) => message.error(String(e)),
  });

  const { data: basisData } = useQuery({
    queryKey: ["report-basis", reportId],
    enabled: !!reportId,
    queryFn: () => api<{ basis: Record<string, unknown> }>(`/reports/${reportId}/basis`),
  });

  const p = refreshComparisonScores(
    normalizeReportPayload((data?.payload ?? {}) as Record<string, unknown>),
  );
  const essayContent = String(data?.submission?.content ?? "").trim();
  const rewriteDemo = p.rewrite_demo as
    | {
        status?: string;
        rewrite_text?: string;
        keep_segments?: { quote: string; reason?: string }[];
        change_summary?: string[];
      }
    | undefined;
  const essayMeta = (p.essay_meta ?? {}) as Record<string, unknown>;
  const standardVersion =
    (p.standard_version as number | undefined) ??
    (essayMeta.standard_version as number | undefined) ??
    (basisData?.basis?.standard_version as number | undefined);
  const examStandardVersion =
    (p.exam_standard_version as number | undefined) ??
    (essayMeta.exam_standard_version as number | undefined) ??
    (basisData?.basis?.exam_standard_version as number | undefined);
  const gradingMode =
    (essayMeta.grading_standard_mode as string | undefined) ??
    (basisData?.basis?.grading_standard_mode as string | undefined);
  const confidence = String(p.confidence ?? "medium");
  const shortCircuit = Boolean(p.short_circuit_reason);
  const displayReferenceOnly = p.display_mode === "reference_only" && shortCircuit;
  const lowScoreConfidence = confidence === "low";
  const confidenceNote =
    (p.confidence_note as string | undefined) ||
    (confidence === "low"
      ? "作文字数明显不足，总分仅供参考；仍可根据维度与建议改进写法。"
      : confidence === "medium"
        ? "总分建议在合理区间内理解；各维度得分与问题、建议可直接用于修改。"
        : "");
  const consensusDiscarded = Boolean(p.consensus_discarded);
  const consensusRan =
    Boolean(p.consensus_ran) ||
    (Array.isArray(p.consensus_scores) && (p.consensus_scores as unknown[]).length >= 2);
  const maxScore = Number(p.max_score ?? 40);
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

  const scoringBasis = {
    ...((p.scoring_basis as Record<string, unknown> | undefined) ?? {}),
    ...(basisData?.basis ?? {}),
    rule_score: basisData?.basis?.rule_score ?? p.rule_score,
    primary_llm_score: basisData?.basis?.primary_llm_score ?? p.primary_llm_score ?? p.total_score,
    llm_score: basisData?.basis?.llm_score ?? p.llm_score ?? p.total_score,
    engine_total_discarded: basisData?.basis?.engine_total_discarded ?? p.engine_total_discarded,
  } as Record<string, unknown>;
  const reviewNotes =
    (p.review_notes as string | undefined) ||
    (scoringBasis.steps_summary as string | undefined) ||
    undefined;

  return (
    <Card
      title="批改报告"
      extra={
        <Space>
          <Button onClick={() => setDisputeOpen(true)}>评分争议</Button>
          <Button>
            <Link to="/reports">全部报告</Link>
          </Button>
        </Space>
      }
    >
      {displayReferenceOnly && (
        <Alert
          type="warning"
          showIcon
          message="评分仅供参考"
          description={String(p.short_circuit_reason)}
          style={{ marginBottom: 16 }}
        />
      )}
      {!displayReferenceOnly && confidenceNote ? (
        <Alert
          type={lowScoreConfidence ? "warning" : "info"}
          showIcon
          message={lowScoreConfidence ? "总分为参考" : "总分数置信度说明"}
          description={confidenceNote}
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <Space wrap align="center">
        <Typography.Title level={2} style={{ margin: 0 }}>
          {displayReferenceOnly ? "—" : String(p.total_score ?? "-")} / {maxScore}
        </Typography.Title>
        {range.length === 2 && (
          <Tag>合理区间 {range[0]}～{range[1]} 分</Tag>
        )}
        <Tag color={CONF_TAG_COLOR[confidence] ?? "blue"}>
          总分数置信度 {CONF_LABEL[confidence] ?? confidence}
        </Tag>
        {consensusRan ? (
          <Tag color={consensusDiscarded ? "default" : "cyan"}>
            {consensusDiscarded ? "双路已检验·采用主评" : "双路已检验"}
          </Tag>
        ) : null}
        {p.from_cache ? <Tag>缓存命中</Tag> : null}
        {p.attempt ? <Tag>第 {String(p.attempt)} 稿</Tag> : null}
        {standardVersion != null ? <Tag color="purple">题目标准 v{standardVersion}</Tag> : null}
        {examStandardVersion != null ? <Tag color="geekblue">考试标准 v{examStandardVersion}</Tag> : null}
        {gradingMode === "default_rubric" ? <Tag>默认 Rubric</Tag> : null}
        {gradingMode === "published" ? <Tag color="green">已发布标准</Tag> : null}
      </Space>

      {comparison && (
        <Alert
          type="success"
          showIcon
          style={{ marginTop: 16 }}
          message={p.attempt && Number(p.attempt) > 2 ? "重作批改对比" : "二次批改对比"}
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
              key: "rewrite",
              label: "改写范例与原文对照",
              children: (
                <ReportRewriteDemo
                  reportId={reportId ?? ""}
                  essayContent={essayContent}
                  rewriteDemo={rewriteDemo}
                  displayReferenceOnly={displayReferenceOnly}
                  onPayloadUpdate={(next) => {
                    qc.setQueryData(["report", reportId], (prev: typeof data) =>
                      prev ? { ...prev, payload: next } : prev,
                    );
                  }}
                />
              ),
            },
            {
              key: "basis",
              label: "查看评分依据",
              children: (
                <ReportScoringBasis
                  basis={scoringBasis}
                  totalScore={displayReferenceOnly ? "—" : String(p.total_score ?? "-")}
                  consensusDiscarded={consensusDiscarded || Boolean(scoringBasis.consensus_discarded)}
                  maxScore={maxScore}
                  confidence={confidence}
                  fromCache={Boolean(p.from_cache)}
                  reviewNotes={reviewNotes}
                  standardVersion={standardVersion ?? null}
                  examStandardVersion={examStandardVersion ?? null}
                  gradingMode={gradingMode}
                />
              ),
            },
          ]}
        />
      </div>

      {(() => {
        const pts = (p.scoring_points as ScoringPoint[]) ?? [];
        const dimSum = pts.reduce((s, it) => s + Number(it.earned ?? 0), 0);
        const totalNum = Number(p.total_score);
        const reconcileNote = p.score_reconcile_note as string | undefined;
        if (
          reconcileNote ||
          (Number.isFinite(dimSum) &&
            Number.isFinite(totalNum) &&
            dimSum > 0 &&
            Math.abs(dimSum - totalNum) > 1.5)
        ) {
          return (
            <Alert
              type="info"
              showIcon
              style={{ marginTop: 16 }}
              message="维度加总与报告总分"
              description={
                reconcileNote ||
                `各维度加总约 ${dimSum.toFixed(1)} 分，报告采用总分为 ${totalNum} 分；以顶部总分为准，维度已做或将在展示时校准。`
              }
            />
          );
        }
        return null;
      })()}

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
            renderItem={(item) => {
              const analysis = issueAnalysisText(item);
              const sev = severityVisual(item.severity);
              return (
                <List.Item>
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Space wrap align="center">
                      <Tag style={issueTypeTagStyle}>{issueBadgeText(item)}</Tag>
                      {item.severity ? <Tag style={sev.style}>{severityLabel(item.severity)}</Tag> : null}
                    </Space>
                    <Typography.Paragraph style={{ marginBottom: 0 }}>{analysis}</Typography.Paragraph>
                    {item.user_quote ? (
                      <Typography.Text type="secondary">你的表述：「{item.user_quote}」</Typography.Text>
                    ) : null}
                  </Space>
                </List.Item>
              );
            }}
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
          <Button
            type="primary"
            block
            style={{ marginTop: 16 }}
            onClick={() => navigate(`/reports/${reportId}/retry`)}
          >
            重新作答
          </Button>
        </Col>
      </Row>
      <Modal
        title="提交评分争议"
        open={disputeOpen}
        onCancel={() => setDisputeOpen(false)}
        onOk={() => submitDispute.mutate()}
        confirmLoading={submitDispute.isPending}
      >
        <Input.TextArea
          rows={4}
          value={disputeReason}
          onChange={(e) => setDisputeReason(e.target.value)}
          placeholder="请说明您认为评分不合理的原因（至少 5 字）"
        />
      </Modal>
    </Card>
  );
}
