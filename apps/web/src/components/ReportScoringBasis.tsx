import { List, Space, Tag, Typography } from "antd";

type RubricRow = {
  id?: string;
  label?: string;
  max_score?: number;
  required?: boolean;
};

type Props = {
  basis: Record<string, unknown>;
  totalScore: number | string;
  maxScore: number;
  confidence: string;
  reviewNotes?: string;
  standardVersion?: number | null;
  examStandardVersion?: number | null;
  gradingMode?: string;
  consensusDiscarded?: boolean;
};

const CONF_ZH: Record<string, string> = { high: "高", medium: "中", low: "参考" };
const CONF_COLOR: Record<string, string> = { high: "green", medium: "blue", low: "gold" };

const MODE_ZH: Record<string, string> = {
  published: "本题已发布的考试标准",
  custom_engine: "根据你的题干与材料生成的评分标准",
  default_rubric: "默认大作文标准（立意、结构、论证、语言）",
};

const EXAM_LEVEL_ZH: Record<string, string> = {
  provincial: "副省级",
  municipal: "市地级",
  enforcement: "行政执法",
};

export default function ReportScoringBasis({
  basis,
  totalScore,
  maxScore,
  confidence,
  reviewNotes,
  gradingMode,
}: Props) {
  const rubric = (basis.scoring_points_rubric as RubricRow[] | undefined) ?? [];
  const evidenceChain =
    (basis.evidence_chain as
      | {
          criterion_id?: string;
          label?: string;
          hit?: string;
          user_quote?: string;
          material_ref?: string;
          earned?: number;
          max?: number;
          reason?: string;
        }[]
      | undefined) ?? [];
  const examLevel = basis.exam_level as string | undefined;

  const standardLine =
    (gradingMode && MODE_ZH[gradingMode]) ||
    (gradingMode === "published" ? MODE_ZH.published : null) ||
    MODE_ZH.default_rubric;

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <div>
        <Typography.Text strong>本次得分</Typography.Text>
        <div style={{ marginTop: 8 }}>
          <Space wrap align="center">
            <Typography.Text>
              {totalScore} / {maxScore} 分
            </Typography.Text>
            <Tag color={CONF_COLOR[confidence] ?? "blue"}>
              总分数置信度 {CONF_ZH[confidence] ?? confidence}
            </Tag>
          </Space>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 8 }}>
            总分与各维度得分、问题与建议来自同一次 AI 批改；请以顶部总分为准理解整卷表现。
          </Typography.Paragraph>
        </div>
      </div>

      {rubric.length > 0 && (
        <div>
          <Typography.Text strong>评分维度（满分 {maxScore}）</Typography.Text>
          <List
            size="small"
            style={{ marginTop: 8 }}
            dataSource={rubric}
            renderItem={(row) => (
              <List.Item>
                <Space>
                  <Typography.Text>{row.label ?? row.id}</Typography.Text>
                  <Typography.Text type="secondary">{row.max_score ?? "—"} 分</Typography.Text>
                  {row.required ? <Tag>必评</Tag> : null}
                </Space>
              </List.Item>
            )}
          />
        </div>
      )}

      <div>
        <Typography.Text strong>标准来源</Typography.Text>
        <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
          {standardLine}
          {examLevel && EXAM_LEVEL_ZH[examLevel] ? ` · 适用卷别：${EXAM_LEVEL_ZH[examLevel]}` : ""}
        </Typography.Paragraph>
      </div>

      {evidenceChain.length > 0 ? (
        <div>
          <Typography.Text strong>要点与原文对应</Typography.Text>
          <List
            size="small"
            style={{ marginTop: 8 }}
            dataSource={evidenceChain.slice(0, 5)}
            renderItem={(row, i) => {
              const max = Number(row.max);
              const earnedRaw = Number(row.earned);
              const earned =
                Number.isFinite(max) && max > 0 && Number.isFinite(earnedRaw)
                  ? Math.min(earnedRaw, max)
                  : row.earned;
              return (
                <List.Item>
                  <Space direction="vertical" size={2} style={{ width: "100%" }}>
                    <Typography.Text>
                      {row.label ?? row.criterion_id ?? `要点 ${i + 1}`}
                      {row.hit
                        ? ` · ${row.hit === "full" ? "命中" : row.hit === "partial" ? "部分命中" : "未命中"}`
                        : ""}
                      {earned != null && row.max != null ? ` · ${earned}/${row.max} 分` : ""}
                    </Typography.Text>
                    {row.user_quote ? (
                      <Typography.Text type="secondary">你的表述：{row.user_quote}</Typography.Text>
                    ) : null}
                    {row.reason ? <Typography.Text type="secondary">{row.reason}</Typography.Text> : null}
                  </Space>
                </List.Item>
              );
            }}
          />
        </div>
      ) : null}

      {reviewNotes ? (
        <div>
          <Typography.Text strong>总评摘录</Typography.Text>
          <Typography.Paragraph style={{ marginTop: 8, marginBottom: 0 }}>{reviewNotes}</Typography.Paragraph>
        </div>
      ) : null}
    </Space>
  );
}
