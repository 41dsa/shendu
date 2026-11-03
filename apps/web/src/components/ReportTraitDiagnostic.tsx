import { Alert, Card, Collapse, List, Space, Tag, Typography } from "antd";
import type { DiagnosticSevenQuestions, TraitDiagnosticRow } from "../utils/traitDiagnostic";
import { traitLevelColor } from "../utils/traitDiagnostic";

const SEVEN_LABELS: { key: keyof DiagnosticSevenQuestions; title: string }[] = [
  { key: "q1_task", title: "1. 这道题要求什么？" },
  { key: "q2_met", title: "2. 这篇作文满足了哪些要求？" },
  { key: "q3_evidence", title: "3. 哪些地方存在证据支持？" },
  { key: "q4_unmet", title: "4. 哪些评分标准没有满足？" },
  { key: "q5_loss", title: "5. 主要失分来源是什么？" },
  { key: "q6_disputes", title: "6. 哪些判断存在标准分歧？" },
  { key: "q7_next", title: "7. 用户下一步怎么改？" },
];

type MultiStandardViews = {
  labels?: { strict?: string; loose?: string; baseline?: string; dependency?: string };
  strict?: { score_min?: number; score_max?: number; system_center?: number; ability_level?: string };
  loose?: { score_min?: number; score_max?: number; system_center?: number; ability_level?: string };
  baseline?: { score_min?: number; score_max?: number; system_center?: number; ability_level?: string };
  dependency?: {
    label?: string;
    traits?: { trait_id: string; name: string; level?: string; dispute_hint?: string }[];
  };
};

type AnchorRelativeScale = {
  nearest_anchor_title?: string;
  distance?: number;
  trait_gaps?: { trait_id: string; essay_level?: string; anchor_level?: string; delta?: number }[];
};

type Props = {
  traits: TraitDiagnosticRow[];
  seven: DiagnosticSevenQuestions;
  abilityLevel: string | null;
  scoreRange: [number, number] | null;
  traitConfidence: number | null;
  disclaimer: string | null;
  hideNumericScore?: boolean;
  scoreDisplayMode?: "tier_only" | "interval" | "center" | null;
  humanReviewRecommended?: boolean;
  multiStandardViews?: MultiStandardViews | null;
  anchorRelativeScale?: AnchorRelativeScale | null;
  anchorCount?: number | null;
  standardDisputeMarks?: string[];
};

function renderAnswer(key: keyof DiagnosticSevenQuestions, seven: DiagnosticSevenQuestions) {
  const val = seven[key];
  if (key === "q1_task") {
    const text = String(val ?? "").trim();
    return text ? (
      <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>{text}</Typography.Paragraph>
    ) : (
      <Typography.Text type="secondary">见上方「作答要求」</Typography.Text>
    );
  }
  const items = Array.isArray(val) ? val : [];
  if (!items.length) {
    return <Typography.Text type="secondary">暂无结构化摘要，请结合下方 Trait 分项查看。</Typography.Text>;
  }
  return (
    <List
      size="small"
      dataSource={items}
      renderItem={(line) => <List.Item style={{ padding: "4px 0", border: "none" }}>{line}</List.Item>}
    />
  );
}

function EvidenceBlock({ title, lines, type }: { title: string; lines: string[]; type?: "secondary" | "danger" | "warning" }) {
  if (!lines.length) return null;
  return (
    <div style={{ marginTop: 6 }}>
      <Typography.Text type={type} strong style={{ fontSize: 12 }}>
        {title}
      </Typography.Text>
      <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
        {lines.map((line, i) => (
          <li key={`${title}-${i}`}>
            <Typography.Text style={{ fontSize: 13 }}>{line}</Typography.Text>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ReportTraitDiagnostic({
  traits,
  seven,
  abilityLevel,
  scoreRange,
  traitConfidence,
  disclaimer,
  hideNumericScore,
  scoreDisplayMode,
  humanReviewRecommended,
  multiStandardViews,
  anchorRelativeScale,
  anchorCount,
  standardDisputeMarks,
}: Props) {
  if (!traits.length) return null;

  const showInterval =
    scoreRange &&
    (scoreDisplayMode === "interval" || scoreDisplayMode === "center" || !hideNumericScore);

  const sevenItems = SEVEN_LABELS.map(({ key, title }) => ({
    key,
    label: title,
    children: renderAnswer(key, seven),
  }));

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%", marginBottom: 24 }}>
      {humanReviewRecommended ? (
        <Alert type="warning" showIcon message="建议人工复核后再采信分数。" />
      ) : null}

      <Card size="small" title="总体判断（Trait V1）">
        <Space wrap>
          {abilityLevel ? <Tag color="processing">能力等级：{abilityLevel}</Tag> : null}
          {scoreDisplayMode === "tier_only" ? <Tag color="default">仅展示等级（未展示精确总分）</Tag> : null}
          {showInterval && scoreDisplayMode !== "tier_only" ? (
            <Tag>
              估计区间 {scoreRange![0]}～{scoreRange![1]} 分
              {scoreDisplayMode === "interval" ? "（未校准）" : ""}
            </Tag>
          ) : null}
          {traitConfidence != null ? <Tag>引擎置信度 {traitConfidence.toFixed(2)}</Tag> : null}
          {multiStandardViews?.baseline?.system_center != null && scoreDisplayMode === "center" ? (
            <Tag color="blue">综合标准中心约 {multiStandardViews.baseline.system_center} 分</Tag>
          ) : null}
        </Space>
        {(standardDisputeMarks?.length ?? 0) > 0 ? (
          <Alert
            type="info"
            showIcon
            style={{ marginTop: 10 }}
            message="标准依赖 / 争议标记"
            description={standardDisputeMarks!.join("；")}
          />
        ) : null}
        {anchorRelativeScale?.nearest_anchor_title ? (
          <Typography.Paragraph type="secondary" style={{ marginTop: 10, marginBottom: 0, fontSize: 12 }}>
            锚作文相对尺度：最接近「{anchorRelativeScale.nearest_anchor_title}」（距离 {anchorRelativeScale.distance ?? "—"}）。
            {anchorCount != null && anchorCount > 0 ? ` 本题已发布锚 ${anchorCount} 篇。` : ""}
          </Typography.Paragraph>
        ) : anchorCount != null && anchorCount > 0 ? (
          <Typography.Paragraph type="secondary" style={{ marginTop: 10, marginBottom: 0, fontSize: 12 }}>
            本题锚作文 {anchorCount} 篇（相对尺度将在匹配成功后展示）。
          </Typography.Paragraph>
        ) : null}
        {multiStandardViews?.strict && multiStandardViews?.loose ? (
          <Card size="small" type="inner" style={{ marginTop: 12 }} title="多标准视图（严格 / 综合 / 宽松）">
            <Space direction="vertical" size={4} style={{ width: "100%" }}>
              {multiStandardViews.baseline ? (
                <Typography.Text style={{ fontSize: 12 }}>
                  {multiStandardViews.labels?.baseline ?? "综合标准"}：
                  {multiStandardViews.baseline.score_min}～{multiStandardViews.baseline.score_max} 分
                  {multiStandardViews.baseline.system_center != null
                    ? `（中心约 ${multiStandardViews.baseline.system_center}）`
                    : ""}
                </Typography.Text>
              ) : null}
              <Typography.Text style={{ fontSize: 12 }}>
                {multiStandardViews.labels?.strict ?? "严格标准"}：
                {multiStandardViews.strict.score_min}～{multiStandardViews.strict.score_max} 分
                {multiStandardViews.strict.system_center != null
                  ? `（中心约 ${multiStandardViews.strict.system_center}）`
                  : ""}
              </Typography.Text>
              <Typography.Text style={{ fontSize: 12 }}>
                {multiStandardViews.labels?.loose ?? "宽松标准"}：
                {multiStandardViews.loose.score_min}～{multiStandardViews.loose.score_max} 分
                {multiStandardViews.loose.system_center != null
                  ? `（中心约 ${multiStandardViews.loose.system_center}）`
                  : ""}
              </Typography.Text>
              {(multiStandardViews.dependency?.traits?.length ?? 0) > 0 ? (
                <>
                  <Typography.Text type="secondary" style={{ fontSize: 12, marginTop: 4 }}>
                    {multiStandardViews.labels?.dependency ??
                      multiStandardViews.dependency?.label ??
                      "标准依赖型维度"}
                  </Typography.Text>
                  <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                    {multiStandardViews.dependency!.traits!.map((t) => (
                      <li key={t.trait_id} style={{ fontSize: 12 }}>
                        {t.trait_id} {t.name}
                        {t.level ? ` · ${t.level}` : ""}
                        {t.dispute_hint ? ` — ${t.dispute_hint}` : ""}
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  C 档 Trait 分项见下方，不参与得分合成。
                </Typography.Text>
              )}
            </Space>
          </Card>
        ) : null}
        {disclaimer ? (
          <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0, fontSize: 12 }}>
            {disclaimer}
          </Typography.Paragraph>
        ) : null}
      </Card>

      <Collapse items={[{ key: "seven", label: "诊断开篇 · 七个必答问题", children: <Collapse items={sevenItems} /> }]} />

      <Typography.Title level={5} style={{ margin: 0 }}>
        八大 Trait 分项诊断
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 8, fontSize: 13 }}>
        B 档 Trait 参与区间合成；C 档（立意高下、分析深度、治理思维）仅诊断、不计入得分。证据均来自原文摘录，便于核验。
      </Typography.Paragraph>

      <List
        grid={{ gutter: 12, column: 1 }}
        dataSource={traits}
        renderItem={(t) => (
          <List.Item>
            <Card size="small" type="inner">
              <Space direction="vertical" size={6} style={{ width: "100%" }}>
                <Space wrap>
                  <Tag>{t.trait_id}</Tag>
                  <Typography.Text strong>{t.name}</Typography.Text>
                  {t.level ? <Tag color={traitLevelColor(t.level)}>{t.level}</Tag> : null}
                  {t.standard_tier === "C" ? <Tag color="purple">争议/仅诊断</Tag> : null}
                  {t.participates_in_score === false ? <Tag>不计分</Tag> : null}
                  {t.evidence_insufficient ? <Tag color="default">证据不足·不展示维度估分</Tag> : null}
                  {t.confidence != null ? (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      置信 {t.confidence.toFixed(2)}
                    </Typography.Text>
                  ) : null}
                </Space>
                {t.conclusion ? (
                  <Typography.Text type="secondary">{t.conclusion}</Typography.Text>
                ) : null}
                <EvidenceBlock title="正向证据" lines={t.evidence_positive} />
                {t.evidence_spans?.some((s) => s.grounded !== false && s.start != null) ? (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    原文定位：
                    {t.evidence_spans
                      .filter((s) => s.grounded !== false && s.start != null)
                      .slice(0, 4)
                      .map((s, i) => (
                        <span key={`${t.trait_id}-sp-${i}`}>
                          {i > 0 ? "；" : ""}
                          第{s.para ?? "?"}段 · 字符 {s.start}–{s.end}
                        </span>
                      ))}
                  </Typography.Text>
                ) : null}
                <EvidenceBlock title="负向证据" lines={t.evidence_negative} type="warning" />
                <EvidenceBlock title="缺失证据" lines={t.evidence_missing} type="danger" />
                {t.dispute_hint ? (
                  <Alert type="info" showIcon message={t.dispute_hint} style={{ marginTop: 4 }} />
                ) : null}
                {t.model_votes && t.model_votes.length > 1 ? (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    模型投票：
                    {t.model_votes.map((v, i) => (
                      <Tag key={i} style={{ marginLeft: 4 }}>
                        {v.model ?? "model"} → {v.level ?? "—"}
                      </Tag>
                    ))}
                  </Typography.Text>
                ) : null}
              </Space>
            </Card>
          </List.Item>
        )}
      />
    </Space>
  );
}
