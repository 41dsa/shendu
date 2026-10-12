import { Descriptions, List, Space, Tag, Typography } from "antd";

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
  fromCache?: boolean;
  reviewNotes?: string;
  standardVersion?: number | null;
  examStandardVersion?: number | null;
  gradingMode?: string;
  consensusDiscarded?: boolean;
};

const CONF_ZH: Record<string, string> = { high: "高", medium: "中", low: "参考" };
const CONF_COLOR: Record<string, string> = { high: "green", medium: "blue", low: "gold" };

/** 考试标准引擎 scoring_rules.score_confidence_declaration */
const SCORE_DECL_ZH: Record<string, string> = {
  high: "较高",
  medium: "中等",
  low: "仅供参考",
};

function scoreConfidenceDeclarationLabel(raw: string): string {
  const key = raw.trim().toLowerCase();
  return SCORE_DECL_ZH[key] ?? raw;
}

const MODE_ZH: Record<string, string> = {
  published: "本题已发布的考试标准（考试标准引擎）",
  custom_engine: "根据你的题干与材料现场生成的评分标准（考试标准引擎 · 自备题）",
  default_rubric: "内置默认大作文四维 Rubric（立意、结构、论证、语言）",
};

function fmtScore(v: unknown): string {
  if (v == null || v === "") return "—";
  const n = Number(v);
  return Number.isFinite(n) ? String(n) : String(v);
}

export default function ReportScoringBasis({
  basis,
  totalScore,
  maxScore,
  confidence,
  fromCache,
  reviewNotes,
  standardVersion,
  examStandardVersion,
  gradingMode,
  consensusDiscarded = false,
}: Props) {
  const ruleScore = basis.rule_score;
  const totalNum = Number(totalScore);
  const basisPrimary = basis.primary_llm_score ?? basis.llm_score;
  const primaryNum = Number(basisPrimary);
  const primaryLlm =
    Number.isFinite(primaryNum) && primaryNum > 0
      ? basisPrimary
      : Number.isFinite(totalNum) && totalNum > 0
        ? totalScore
        : basisPrimary ?? totalScore;
  const basisFinal = basis.llm_score;
  const basisFinalNum = Number(basisFinal);
  const finalLlm =
    Number.isFinite(basisFinalNum) && basisFinalNum > 0
      ? basisFinal
      : Number.isFinite(totalNum) && totalNum > 0
        ? totalScore
        : basisFinal ?? totalScore;
  const engineDiscarded = Boolean(basis.engine_total_discarded);
  const consensus = (basis.consensus_scores as number[] | undefined) ?? [];
  const consensusDelta = basis.consensus_delta as number | null | undefined;
  const discarded = consensusDiscarded || Boolean(basis.consensus_discarded);
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
  const scoreDecl = basis.score_confidence_declaration as string | undefined;

  const ruleNum = Number(ruleScore);
  const finalNum = Number(finalLlm);
  const scoreGap =
    Number.isFinite(ruleNum) && Number.isFinite(finalNum) ? Math.abs(ruleNum - finalNum) : null;

  let scoreExplain = "总分以完整批改主评为准，并与下方各维度说明一致；合理区间供估分参考。";
  if (fromCache) {
    scoreExplain = "本次命中历史批改缓存，总分与维度与上次相同题目、相同正文的结果一致。";
  } else if (discarded) {
    scoreExplain =
      "系统曾做内部分歧检测，复核分与主评差距过大已自动忽略，避免误导；请以主评总分与维度反馈为准。";
  } else if (scoreGap != null && scoreGap <= 1) {
    scoreExplain += " 规则预评与 AI 接近，置信度较高。";
  } else if (scoreGap != null && scoreGap > 1) {
    scoreExplain += ` 规则预评（程序估算）与 AI 相差约 ${scoreGap.toFixed(1)} 分，属正常校验差异。`;
  }

  const standardLines: string[] = [];
  if (gradingMode && MODE_ZH[gradingMode]) {
    standardLines.push(MODE_ZH[gradingMode]);
  } else if (gradingMode === "published") {
    standardLines.push("本题已发布的考试标准");
  }
  if (standardVersion != null) {
    standardLines.push(`题目级标准版本：v${standardVersion}`);
  }
  if (examStandardVersion != null) {
    standardLines.push(`考试级标准版本：v${examStandardVersion}`);
  }
  if (standardLines.length === 0) {
    standardLines.push("未绑定已发布标准时，使用内置默认 Rubric。");
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <div>
        <Typography.Text strong>总分怎么来的</Typography.Text>
        <Descriptions column={1} size="small" style={{ marginTop: 8 }}>
          <Descriptions.Item label="规则预评">
            {fmtScore(ruleScore)} 分
            <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
              {engineDiscarded && Number(ruleScore) <= 0
                ? "本次要点匹配不足，未产生有效规则分；报告总分以完整批改主评为准"
                : "按字数、结构与维度做的程序估算，用于校验 AI 结果"}
            </Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="AI 批改总分">{fmtScore(primaryLlm)} 分</Descriptions.Item>
          <Descriptions.Item label="报告采用">
            {totalScore} / {maxScore} 分
            {!discarded && consensus.length >= 2 && consensusDelta != null && consensusDelta > 1 ? (
              <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                （与轻量复核平均：{fmtScore(finalLlm)}）
              </Typography.Text>
            ) : null}
          </Descriptions.Item>
          <Descriptions.Item label="总分数置信度">
            <Tag color={CONF_COLOR[confidence] ?? "blue"}>{CONF_ZH[confidence] ?? confidence}</Tag>
            <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
              指总分估算可信度；维度分析与建议不受此限制
            </Typography.Text>
          </Descriptions.Item>
          {discarded ? (
            <Descriptions.Item label="质量校验">
              双路总分差距较大，报告采用主评/合并结果
              {basis.consensus_review_score != null
                ? `（复核分 ${fmtScore(basis.consensus_review_score)} 未采用）`
                : ""}
              。
            </Descriptions.Item>
          ) : consensus.length >= 2 ? (
            <Descriptions.Item label="轻量复核">
              主评与规则预评接近时，系统曾做第二次仅总分校验
              {consensusDelta != null && consensusDelta <= 1.5
                ? "，与主评基本一致。"
                : "，结果已纳入平均。"}
            </Descriptions.Item>
          ) : (
            <Descriptions.Item label="双路复核">
              未执行第二次总分检验。常见原因：已开启省流模式，或作文字数明显不足。
            </Descriptions.Item>
          )}
        </Descriptions>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 8 }}>
          {scoreExplain}
        </Typography.Paragraph>
      </div>

      {rubric.length > 0 && (
        <div>
          <Typography.Text strong>评分维度设置（满分 {maxScore}）</Typography.Text>
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
        <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
          {standardLines.map((line) => (
            <li key={line}>
              <Typography.Text type="secondary">{line}</Typography.Text>
            </li>
          ))}
        </ul>
      </div>

      {evidenceChain.length > 0 ? (
        <div>
          <Typography.Text strong>评分证据链</Typography.Text>
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
                    {row.hit ? ` · ${row.hit === "full" ? "命中" : row.hit === "partial" ? "部分命中" : "未命中"}` : ""}
                    {earned != null && row.max != null ? ` · 要点 ${earned}/${row.max} 分` : ""}
                  </Typography.Text>
                  {row.user_quote ? (
                    <Typography.Text type="secondary">你的表述：{row.user_quote}</Typography.Text>
                  ) : null}
                  {row.material_ref ? (
                    <Typography.Text type="secondary">作文定位：{row.material_ref}</Typography.Text>
                  ) : null}
                  {row.reason ? <Typography.Text type="secondary">{row.reason}</Typography.Text> : null}
                </Space>
              </List.Item>
            );
            }}
          />
        </div>
      ) : null}

      {scoreDecl ? (
        <Typography.Text type="secondary">
          标准分值说明：{scoreConfidenceDeclarationLabel(scoreDecl)}（非官方阅卷尺度）
        </Typography.Text>
      ) : null}

      {reviewNotes ? (
        <div>
          <Typography.Text strong>阅卷总评摘录</Typography.Text>
          <Typography.Paragraph style={{ marginTop: 8, marginBottom: 0 }}>{reviewNotes}</Typography.Paragraph>
        </div>
      ) : null}
    </Space>
  );
}
