import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Input,
  List,
  Modal,
  Row,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import ReportRequirementScoring from "../components/ReportRequirementScoring";
import ReportReferenceSample from "../components/ReportReferenceSample";
import ReportRewriteDemo from "../components/ReportRewriteDemo";
import ReportScoringBasis from "../components/ReportScoringBasis";
import {
  normalizeReportPayload,
  parseScoreValue,
  refreshComparisonScores,
  resolveReviewNotesDisplay,
  resolveScoreConfidenceRange,
  resolveScoringPointHit,
} from "../utils/reportPayload";
import EssayHighlightView from "../components/EssayHighlightView";
import ReportDimensionCriteria from "../components/ReportDimensionCriteria";
import ReportTraitDiagnostic from "../components/ReportTraitDiagnostic";
import ReportPrdDisclaimer from "../components/ReportPrdDisclaimer";
import {
  isTraitV1Report,
  parseDiagnosticHeader,
  parseTraitDiagnostics,
  resolveAbilityLevel,
  resolveHumanReviewRecommended,
  resolveHumanReviewNote,
  resolveStandardDisputeMarks,
  resolveAnchorCount,
  resolveAnchorRelativeScale,
  resolveMultiStandardViews,
  resolveScoreDisclaimer,
  resolveScoreDisplayMode,
  resolveTraitConfidence,
} from "../utils/traitDiagnostic";
import ReportEssayExcerpt from "../components/ReportEssayExcerpt";
import { issueAnalysisText, issueBadgeText, issueComparisonKey } from "../utils/issueDisplay";
import { resolveIssueExcerptDisplay } from "../utils/essayLocate";
import { primaryIssueAnchorQuote } from "../utils/issueAnchor";
import {
  collectEssayRewriteMarkRanges,
  highlightRangesForIssue,
} from "../utils/rewriteMarkSpans";
import { criteriaHitsForDisplay, parsePointHitsFromPayload } from "../utils/dimensionCriteria";
import { formatSuggestionLine } from "../utils/suggestionDisplay";
import { issueTypeTagStyle, severityLabel, severityVisual } from "../utils/severityLabel";

type ScoringPoint = {
  id?: string;
  label?: string;
  earned?: number;
  max?: number;
  hit?: string;
  reason?: string;
  material_ref?: string;
  user_quote?: string;
  evidence_ref?: string;
};

type Issue = {
  tag?: string;
  issue_title?: string;
  severity?: string;
  explanation?: string;
  user_quote?: string;
  material_ref?: string;
  solution_example?: string;
  rewrite_mark_spans?: { start: number; end: number }[];
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

function issueEssayExcerpt(
  essay: string,
  item: Issue,
  editSegments?: { quote?: string; source_quote?: string; issue_tag?: string; reason?: string }[],
): { text: string; ranges: import("../utils/highlightEssay").HighlightRange[] } | null {
  const anchorQuote = primaryIssueAnchorQuote(essay, item);
  let markSpans = item.rewrite_mark_spans;
  if (!markSpans?.length) {
    markSpans = highlightRangesForIssue(essay, item, editSegments).map((r) => ({
      start: r.start,
      end: r.end,
    }));
  }
  const view = resolveIssueExcerptDisplay(
    essay,
    [anchorQuote, item.user_quote],
    [item.explanation],
    {
      materialRef: item.material_ref,
      markSpans,
    },
  );
  if (!view) return null;
  return { text: view.body, ranges: view.ranges };
}

export default function ReportPage() {
  const { reportId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [disputeOpen, setDisputeOpen] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");
  const [reportCollapseKeys, setReportCollapseKeys] = useState<string[]>([]);
  const { data } = useQuery({
    queryKey: ["report", reportId],
    enabled: !!reportId,
    queryFn: () =>
      api<{
        id: string;
        payload: Record<string, unknown>;
        submission?: {
          content?: string;
          user_prompt?: string | null;
          user_material?: string | null;
          question_title?: string | null;
          is_custom?: boolean;
          attempt?: number;
        };
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
  const essayMeta = (p.essay_meta ?? {}) as Record<string, unknown>;
  const essayContent = String(data?.submission?.content ?? "").trim();
  const reportPrompt =
    String(data?.submission?.user_prompt ?? "").trim() ||
    String(essayMeta.prompt_excerpt ?? "").trim();
  const reportMaterial = String(data?.submission?.user_material ?? "").trim();
  const reportQuestionTitle =
    String(data?.submission?.question_title ?? "").trim() ||
    String(essayMeta.title ?? "").trim() ||
    "";
  const referenceSample = p.reference_sample as
    | {
        status?: string;
        schema_version?: number;
        sample_text?: string;
        target_tier_note?: string;
        body_theses?: { index?: number; title?: string }[];
        mark_segments?: {
          quote?: string;
          point_label?: string;
          thesis_index?: number;
          why?: string;
        }[];
      }
    | undefined;
  const rewriteDemo = p.rewrite_demo as
    | {
        status?: string;
        rewrite_text?: string;
        keep_segments?: { quote: string; reason?: string }[];
        edit_segments?: { quote?: string; reason?: string; issue_tag?: string }[];
        change_summary?: string[];
        validation_check?: {
          issue_fix_status?: { tag?: string; edit_indexes?: number[] }[];
        };
      }
    | undefined;
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
  const traitV1 = isTraitV1Report(p);
  const abilityLevel = resolveAbilityLevel(p);
  const traitDisclaimer = resolveScoreDisclaimer(p);
  const traitConfidence = resolveTraitConfidence(p);
  const engBlock = p.scoring_engine as Record<string, unknown> | undefined;
  const traitIntervalRaw = (p.score_range as number[] | undefined) ??
    (engBlock?.score_interval as number[] | undefined);
  const traitScoreRange =
    Array.isArray(traitIntervalRaw) && traitIntervalRaw.length >= 2
      ? ([Number(traitIntervalRaw[0]), Number(traitIntervalRaw[1])] as [number, number])
      : null;
  const scoreDisplayMode =
    (p.score_display_mode as string | undefined) ??
    (engBlock?.score_display_mode as string | undefined);
  const intervalOnly =
    p.display_mode === "interval_only" || scoreDisplayMode === "interval";
  const hideNumericTotal =
    p.display_mode === "reference_only" ||
    scoreDisplayMode === "tier_only" ||
    Boolean(p.trait_low_confidence) ||
    shortCircuit;
  const displayReferenceOnly = hideNumericTotal && !intervalOnly;
  const humanReviewRecommended = resolveHumanReviewRecommended(p);
  const humanReviewNote = resolveHumanReviewNote(p);
  const standardDisputeMarks = resolveStandardDisputeMarks(p);
  const multiStandardViews = resolveMultiStandardViews(p);
  const anchorRelativeScale = resolveAnchorRelativeScale(p);
  const anchorCount = resolveAnchorCount(p);
  const resolvedScoreDisplayMode = resolveScoreDisplayMode(p);
  const lowScoreConfidence = confidence === "low";
  const rawConfidenceNote = String(p.confidence_note ?? "").trim();
  const confidenceNote =
    rawConfidenceNote.includes("规则引擎") ? "" : rawConfidenceNote;
  const showConfidenceAlert = !displayReferenceOnly && confidence === "low";
  const consensusDiscarded = Boolean(p.consensus_discarded);
  const consensusRan =
    Boolean(p.consensus_ran) ||
    (Array.isArray(p.consensus_scores) && (p.consensus_scores as unknown[]).length >= 2);
  const maxScore = Number(p.display_max_score ?? p.max_score ?? 40);
  const systemMaxScore =
    p.max_score_system != null ? Number(p.max_score_system) : Number(p.max_score ?? 40);
  const showDualMax =
    p.display_max_score != null &&
    systemMaxScore > 0 &&
    Math.abs(Number(p.display_max_score) - systemMaxScore) >= 1;
  const gradeByRequirements = String(p.grade_by_requirements ?? "").trim();
  const gradeBand = String(p.grade_band_by_requirements ?? "").trim();
  const totalForRange = displayReferenceOnly ? null : parseScoreValue(p.total_score);
  const range = resolveScoreConfidenceRange(
    totalForRange ?? p.total_score,
    maxScore,
    confidence,
    p.score_range,
  );
  const retrySubmitAllowed = p.retry_submit_allowed !== false;
  const retryMaxCount = Math.max(1, Number(p.retry_max_count) || 1);
  const retryUsedCount = Math.max(0, Number(p.retry_used_count) || 0);
  const firstPassTierLabel = p.first_pass_tier_label ? String(p.first_pass_tier_label) : "";
  const comparison = p.comparison as
    | {
        first_score?: number;
        second_score?: number;
        score_delta?: number;
        first_hit_rate?: number;
        second_hit_rate?: number;
        hit_rate_delta?: number;
        score_unchanged_note?: string | null;
        issue_changes?: { tag?: string; label?: string; status?: string }[];
      }
    | undefined;
  const retryTierLift = p.retry_tier_lift as
    | {
        tier_before?: string;
        tier_after?: string;
        baseline_score?: number;
        applied_score?: number;
      }
    | undefined;

  const ISSUE_STATUS: Record<string, string> = {
    improved: "已改善",
    resolved: "已解决",
    unchanged: "仍待改进",
    worse: "加重",
    new: "新出现",
  };

  function issueChangeStatus(item: Issue): string | null {
    const key = issueComparisonKey(item);
    if (key) {
      const row = (comparison?.issue_changes ?? []).find((r) => String(r.tag ?? "").trim() === key);
      const status = row?.status;
      if (status && status !== "resolved") return status;
    }
    const title = (item.issue_title ?? "").trim();
    const badge = issueBadgeText(item);
    for (const row of comparison?.issue_changes ?? []) {
      const status = row.status;
      if (!status || status === "resolved") continue;
      const rowLabel = String(row.label ?? "").trim();
      if (title && rowLabel === title) return status;
      if (badge && rowLabel === badge) return status;
    }
    return null;
  }

  const scoringBasis = {
    ...((p.scoring_basis as Record<string, unknown> | undefined) ?? {}),
    ...(basisData?.basis ?? {}),
    rule_score: basisData?.basis?.rule_score ?? p.rule_score,
    primary_llm_score: basisData?.basis?.primary_llm_score ?? p.primary_llm_score ?? p.total_score,
    llm_score: basisData?.basis?.llm_score ?? p.llm_score ?? p.total_score,
    engine_total_discarded: basisData?.basis?.engine_total_discarded ?? p.engine_total_discarded,
  } as Record<string, unknown>;
  const reviewNotes = resolveReviewNotesDisplay(
    p,
    scoringBasis.steps_summary as string | undefined,
  );

  useEffect(() => {
    setReportCollapseKeys([]);
  }, [reportId]);

  const mainIssues = (p.issues as Issue[]) ?? [];
  const retryMajorIssues = (p.retry_major_issues as Issue[]) ?? [];
  const attemptN = Math.max(Number(data?.submission?.attempt) || 0, Number(p.attempt) || 0) || 1;
  const isSecondPass = attemptN >= 2;
  const rewriteDemoReady = rewriteDemo?.status === "ready" && Boolean(rewriteDemo?.rewrite_text?.trim());
  const showRewriteCollapse =
    !displayReferenceOnly &&
    (!isSecondPass || retryMajorIssues.length > 0 || rewriteDemoReady);
  const comparisonIssueRows = useMemo(() => {
    if (!isSecondPass) return [];
    const rows = comparison?.issue_changes ?? [];
    return rows.filter((row) => row?.label || row?.tag);
  }, [isSecondPass, comparison?.issue_changes]);
  const showComparisonIssuesFallback =
    isSecondPass && mainIssues.length === 0 && retryMajorIssues.length === 0 && comparisonIssueRows.length > 0;
  const editSegmentsForMarks =
    (rewriteDemo?.edit_segments as { quote?: string; source_quote?: string; issue_tag?: string; reason?: string }[]) ??
    undefined;

  const enginePointHits = useMemo(() => parsePointHitsFromPayload(p), [p]);

  const traitRows = useMemo(() => parseTraitDiagnostics(p), [p]);
  const traitSuggestions = useMemo(
    () =>
      (Array.isArray(p.suggestions) ? p.suggestions : [])
        .map((s) => String(s).trim())
        .filter(Boolean),
    [p.suggestions],
  );
  const diagnosticSeven = useMemo(
    () => parseDiagnosticHeader(p, { prompt: reportPrompt, suggestions: traitSuggestions }),
    [p, reportPrompt, traitSuggestions],
  );

  const essayRewriteMarkRanges = useMemo(
    () =>
      collectEssayRewriteMarkRanges(
        essayContent,
        [...mainIssues, ...retryMajorIssues],
        (rewriteDemo?.edit_segments as { quote?: string; source_quote?: string; issue_tag?: string; reason?: string }[]) ??
          undefined,
      ),
    [essayContent, mainIssues, retryMajorIssues, rewriteDemo?.edit_segments],
  );

  useEffect(() => {
    if (essayContent && !displayReferenceOnly) {
      setReportCollapseKeys((prev) => (prev.includes("essay") ? prev : [...prev, "essay"]));
    }
  }, [reportId, essayContent, displayReferenceOnly]);

  const reportCollapseItems = useMemo(() => {
    const contextItem = {
      key: "context",
      label: "作答要求与给定材料",
      children: (
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          {reportQuestionTitle ? (
            <Typography.Text type="secondary">题目：{reportQuestionTitle}</Typography.Text>
          ) : null}
          <div>
            <Typography.Text strong>作答要求</Typography.Text>
            {reportPrompt ? (
              <Input.TextArea
                readOnly
                value={reportPrompt}
                autoSize={{ minRows: 3, maxRows: 16 }}
                style={{ marginTop: 8, fontSize: 14 }}
              />
            ) : (
              <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
                未保留题干文本（多为旧版报告）；可在「改写范例」中查看你的作文原文。
              </Typography.Paragraph>
            )}
          </div>
          <div>
            <Typography.Text strong>给定材料</Typography.Text>
            {reportMaterial ? (
              <Input.TextArea
                readOnly
                value={reportMaterial}
                autoSize={{ minRows: 4, maxRows: 20 }}
                style={{ marginTop: 8, fontSize: 14 }}
              />
            ) : (
              <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
                本题未附带给定材料，或提交时未填写材料。
              </Typography.Paragraph>
            )}
          </div>
        </Space>
      ),
    };
    const basisItem = {
      key: "basis",
      label: "查看评分依据",
      children: (
        <ReportScoringBasis
          basis={scoringBasis}
          totalScore={displayReferenceOnly ? "—" : String(p.total_score ?? "-")}
          consensusDiscarded={consensusDiscarded || Boolean(scoringBasis.consensus_discarded)}
          maxScore={maxScore}
          confidence={confidence}
          reviewNotes={reviewNotes}
          standardVersion={standardVersion ?? null}
          examStandardVersion={examStandardVersion ?? null}
          gradingMode={gradingMode}
        />
      ),
    };
    const items = [contextItem];
    if (essayContent && !displayReferenceOnly) {
      items.push({
        key: "essay",
        label: isSecondPass ? (attemptN > 2 ? `第 ${attemptN} 稿原文` : "本稿原文") : "作答原文",
        children: (
          <div>
            {essayRewriteMarkRanges.length > 0 ? (
              <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
                红色高亮为「主要问题」对应的原文位置
              </Typography.Text>
            ) : isSecondPass && mainIssues.length === 0 && retryMajorIssues.length === 0 ? (
              <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
                本轮无待改问题，以下为最终稿正文。
              </Typography.Text>
            ) : null}
            <EssayHighlightView
              content={essayContent}
              ranges={essayRewriteMarkRanges}
              highlightBg="#ffa39e"
              highlightTitle="问题对应原文"
              issueMarkHighlight
              preserveOriginalLayout
              emptyLabel="暂无作答正文"
              panelBg="#fff"
              borderColor="#f0f0f0"
            />
          </div>
        ),
      });
    }
    if (showRewriteCollapse) {
      items.push({
        key: "rewrite",
        label: isSecondPass ? "待继续改进 · 改写范例与原文对照（按需）" : "改写范例与原文对照",
        children: (
          <ReportRewriteDemo
            reportId={reportId ?? ""}
            essayContent={essayContent}
            rewriteDemo={rewriteDemo}
            displayReferenceOnly={displayReferenceOnly}
            scope={isSecondPass ? "retry_major" : "first_pass"}
            onPayloadUpdate={(next) => {
              qc.setQueryData(["report", reportId], (prev: typeof data) =>
                prev ? { ...prev, payload: next } : prev,
              );
            }}
          />
        ),
      });
    }
    items.push(basisItem);
    if (!displayReferenceOnly) {
      items.push({
        key: "reference_sample",
        label: "参考示例- AI生成-仅供参考",
        children: (
          <ReportReferenceSample
            reportId={reportId ?? ""}
            referenceSample={referenceSample}
            displayReferenceOnly={displayReferenceOnly}
            onPayloadUpdate={(next) => {
              qc.setQueryData(["report", reportId], (prev: typeof data) =>
                prev ? { ...prev, payload: next } : prev,
              );
            }}
          />
        ),
      });
    }
    return items;
  }, [
    reportQuestionTitle,
    reportPrompt,
    reportMaterial,
    referenceSample,
    showRewriteCollapse,
    isSecondPass,
    attemptN,
    mainIssues.length,
    retryMajorIssues.length,
    rewriteDemoReady,
    reportId,
    essayContent,
    rewriteDemo,
    displayReferenceOnly,
    scoringBasis,
    p.total_score,
    consensusDiscarded,
    maxScore,
    confidence,
    reviewNotes,
    standardVersion,
    examStandardVersion,
    gradingMode,
    qc,
    data,
    essayRewriteMarkRanges,
  ]);

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
      {shortCircuit && (
        <Alert
          type="warning"
          showIcon
          message="评分仅供参考"
          description={String(p.short_circuit_reason)}
          style={{ marginBottom: 16 }}
        />
      )}
      {traitV1 ? (
        <ReportPrdDisclaimer
          disclaimer={traitDisclaimer}
          nonOfficialNotice={String(p.non_official_notice ?? "")}
        />
      ) : null}

      {traitV1 && humanReviewRecommended && !shortCircuit ? (
        <Alert
          type="warning"
          showIcon
          message="建议人工复核"
          description={
            humanReviewNote ||
            "引擎置信度偏低或模型分歧较大，请勿将分数当作精确估分，重点阅读 Trait 证据与修改建议。"
          }
          style={{ marginBottom: 16 }}
        />
      ) : null}
      {traitV1 && Boolean(p.trait_low_confidence) && !shortCircuit && !humanReviewRecommended ? (
        <Alert
          type="info"
          showIcon
          message="建议以 Trait 诊断为主"
          description="本题置信度偏低或未校准，精确总分已隐藏；请重点阅读八大 Trait 证据与修改建议。"
          style={{ marginBottom: 16 }}
        />
      ) : null}
      {showConfidenceAlert ? (
        <Alert
          type="warning"
          showIcon
          message="总分为参考"
          description={
            confidenceNote ||
            "作文字数明显不足，总分仅供参考；仍可根据维度与建议改进写法。"
          }
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {traitV1 && traitRows.length > 0 ? (
        <ReportTraitDiagnostic
          traits={traitRows}
          seven={diagnosticSeven}
          abilityLevel={abilityLevel}
          scoreRange={traitScoreRange ?? range}
          traitConfidence={traitConfidence}
          disclaimer={traitDisclaimer}
          hideNumericScore={hideNumericTotal && !intervalOnly}
          scoreDisplayMode={resolvedScoreDisplayMode}
          humanReviewRecommended={humanReviewRecommended}
          multiStandardViews={multiStandardViews}
          anchorRelativeScale={anchorRelativeScale}
          anchorCount={anchorCount}
          standardDisputeMarks={standardDisputeMarks}
        />
      ) : null}

      <Space wrap align="center">
        <Typography.Title level={2} style={{ margin: 0 }}>
          {hideNumericTotal ? "—" : String(p.total_score ?? "-")} / {maxScore}
        </Typography.Title>
        {abilityLevel && traitV1 ? <Tag color="processing">能力 {abilityLevel}</Tag> : null}
        {(intervalOnly || (range && !hideNumericTotal)) && traitScoreRange ? (
          <Tag>
            估计区间 {traitScoreRange[0]}～{traitScoreRange[1]} 分
            {intervalOnly ? "（未校准，不展示中心分）" : ""}
          </Tag>
        ) : null}
        {range && !hideNumericTotal && !intervalOnly ? (
          <Tag>合理区间 {range[0]}～{range[1]} 分</Tag>
        ) : null}
        <Tag color={CONF_TAG_COLOR[confidence] ?? "blue"}>
          总分数置信度 {CONF_LABEL[confidence] ?? confidence}
        </Tag>
        {consensusRan ? (
          <Tag color={consensusDiscarded ? "default" : "cyan"}>
            {consensusDiscarded ? "双路已检验·采用主评" : "双路已检验"}
          </Tag>
        ) : null}
        {p.attempt ? <Tag>第 {String(p.attempt)} 稿</Tag> : null}
        {standardVersion != null ? <Tag color="purple">题目标准 v{standardVersion}</Tag> : null}
        {examStandardVersion != null ? <Tag color="geekblue">考试标准 v{examStandardVersion}</Tag> : null}
        {gradingMode === "default_rubric" ? <Tag>默认 Rubric</Tag> : null}
        {gradingMode === "published" ? <Tag color="green">已发布标准</Tag> : null}
        {gradeByRequirements ? (
          <Tag color="processing">
            {gradeByRequirements}
            {gradeBand ? `（${gradeBand} 分）` : ""}
          </Tag>
        ) : null}
        {showDualMax ? (
          <Tag color="default">系统 Rubric 满分 {systemMaxScore} 分</Tag>
        ) : null}
      </Space>

      {!displayReferenceOnly ? (
        <ReportRequirementScoring
          summary={p.requirement_scoring as { rows?: unknown[] } | undefined}
        />
      ) : null}

      {reviewNotes?.trim() && !displayReferenceOnly ? (
        <div style={{ marginTop: 16 }}>
          <Typography.Text strong>总评摘录</Typography.Text>
          <Typography.Paragraph style={{ marginTop: 8, marginBottom: 0, whiteSpace: "pre-wrap" }}>
            {reviewNotes}
          </Typography.Paragraph>
        </div>
      ) : null}

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
                维度达标率 {comparison.first_hit_rate}% → {comparison.second_hit_rate}%（
                {comparison.hit_rate_delta != null && comparison.hit_rate_delta >= 0 ? "+" : ""}
                {comparison.hit_rate_delta}%）
              </span>
              {retryTierLift?.tier_after ? (
                <Typography.Text type="secondary">
                  改进后已按规则升档：{retryTierLift.tier_before ?? "—"} → {retryTierLift.tier_after}
                  {retryTierLift.baseline_score != null && retryTierLift.applied_score != null
                    ? `（${retryTierLift.baseline_score} → ${retryTierLift.applied_score} 分）`
                    : ""}
                </Typography.Text>
              ) : comparison.score_unchanged_note ? (
                <Typography.Text type="secondary">{comparison.score_unchanged_note}</Typography.Text>
              ) : null}
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

      <div id="report-collapse-panel" style={{ marginTop: 16 }}>
        <Collapse
          activeKey={reportCollapseKeys}
          onChange={(keys) => setReportCollapseKeys(Array.isArray(keys) ? keys : [keys])}
          items={reportCollapseItems}
        />
      </div>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={14}>
          <Typography.Title level={5}>{traitV1 ? "兼容维度视图" : "各维度得分"}</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 12, fontSize: 13 }}>
            {traitV1
              ? "下列条目由八大 Trait 映射，便于与旧版能力维度对照；正式诊断以上方 Trait 分项与证据为准。"
              : "维度分用于看强弱分布；顶部总分为整卷结论。若某一维显示 0 分而总分不低，多为自动采分未检出该维要点，可结合总评与下方说明理解。"}
          </Typography.Paragraph>
          <List
            grid={{ gutter: 8, column: 1 }}
            dataSource={(p.scoring_points as ScoringPoint[]) ?? []}
            renderItem={(item) => {
              const { scored: criteriaHits, missedCount: criteriaMissed } = criteriaHitsForDisplay(
                item,
                enginePointHits,
              );
              const dimHit = resolveScoringPointHit(item.earned, item.max, item.hit);
              const dimEarned = Number(item.earned ?? 0);
              const dimMax = Number(item.max ?? 0);
              const showZeroDimNote =
                !displayReferenceOnly &&
                dimMax > 0 &&
                dimEarned <= 0 &&
                Number(p.total_score ?? 0) >= dimMax * 0.35;
              return (
              <List.Item>
                <Card size="small" type="inner">
                  <Space direction="vertical" size={4}>
                    <Space>
                      <Tag color={HIT_COLOR[dimHit] ?? "default"}>
                        {HIT_LABEL[dimHit] ?? dimHit}
                      </Tag>
                      <Typography.Text strong>{item.label}</Typography.Text>
                      <Typography.Text>
                        {item.earned}/{item.max} 分
                      </Typography.Text>
                    </Space>
                    {showZeroDimNote ? (
                      <Typography.Text type="warning" style={{ fontSize: 12 }}>
                        自动采分在该维度未检出得分；若总评或主评说明与此不符，请以顶部总分与总评为准，或查看「评分依据」。
                      </Typography.Text>
                    ) : null}
                    {item.reason && item.reason !== "确定性引擎按采分点覆盖率聚合" ? (
                      <Typography.Text type="secondary">{item.reason}</Typography.Text>
                    ) : null}
                    <ReportDimensionCriteria
                      hits={criteriaHits}
                      missedCount={criteriaMissed}
                      dimensionEarned={dimEarned}
                    />
                    {item.evidence_ref || item.material_ref ? (
                      <Typography.Text type="secondary">
                        依据：{item.evidence_ref ?? item.material_ref}
                      </Typography.Text>
                    ) : null}
                  </Space>
                </Card>
              </List.Item>
              );
            }}
          />
        </Col>
        <Col span={10}>
          <Typography.Title level={5}>主要问题</Typography.Title>
          {showComparisonIssuesFallback ? (
            <Typography.Paragraph type="secondary" style={{ marginBottom: 8, fontSize: 13 }}>
              无轻微档残留；以下为与上一稿对比的问题变化（已解决/已改善项仍保留记录）。
            </Typography.Paragraph>
          ) : null}
          {p.retry_issue_policy_ok === false ? (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message="改写尚未达标"
              description={String(p.retry_issue_policy_message ?? "仍存在中等及以上问题，请继续修改后再提交。")}
            />
          ) : null}
          <List
            dataSource={
              showComparisonIssuesFallback
                ? []
                : ((p.issues as Issue[]) ?? [])
            }
            locale={{
              emptyText:
                showComparisonIssuesFallback
                  ? ""
                  : Number(p.attempt) >= 2
                    ? "无轻微档残留问题"
                    : "暂无结构化问题标签",
            }}
            renderItem={(item, index) => {
              const analysis = issueAnalysisText(item);
              const sev = severityVisual(item.severity);
              const change = issueChangeStatus(item);
              const excerpt = issueEssayExcerpt(essayContent, item, editSegmentsForMarks);
              const issueTitle = issueBadgeText(item);
              return (
                <List.Item>
                  <div
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      borderRadius: 8,
                      border: "1px solid #f0f0f0",
                    }}
                  >
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Space wrap align="center" size={6}>
                      <Typography.Text strong>{issueTitle}</Typography.Text>
                      {change ? (
                        <Tag color={change === "new" ? "orange" : change === "worse" ? "red" : "default"}>
                          {ISSUE_STATUS[change] ?? change}
                        </Tag>
                      ) : null}
                      {item.severity ? <Tag style={sev.style}>{severityLabel(item.severity)}</Tag> : null}
                    </Space>
                    <Typography.Paragraph style={{ marginBottom: 0 }}>{analysis}</Typography.Paragraph>
                    {excerpt ? (
                      <ReportEssayExcerpt excerpt={excerpt.text} highlightRanges={excerpt.ranges} />
                    ) : null}
                  </Space>
                  </div>
                </List.Item>
              );
            }}
          />
          {showComparisonIssuesFallback ? (
            <List
              dataSource={comparisonIssueRows}
              renderItem={(row) => {
                const status = String(row.status ?? "").trim();
                const label = String(row.label ?? row.tag ?? "问题").trim();
                const statusColor =
                  status === "resolved" || status === "improved"
                    ? "success"
                    : status === "worse"
                      ? "error"
                      : status === "new"
                        ? "orange"
                        : "default";
                return (
                  <List.Item>
                    <div
                      style={{
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: 8,
                        border: "1px solid #f0f0f0",
                      }}
                    >
                      <Space wrap align="center" size={6}>
                        <Typography.Text strong>{label}</Typography.Text>
                        {status ? (
                          <Tag color={statusColor}>{ISSUE_STATUS[status] ?? status}</Tag>
                        ) : null}
                      </Space>
                    </div>
                  </List.Item>
                );
              }}
            />
          ) : null}
          {Array.isArray(p.retry_major_issues) && (p.retry_major_issues as Issue[]).length > 0 ? (
            <>
              <Typography.Title level={5} style={{ marginTop: 16 }}>
                待继续改进（中等及以上）
              </Typography.Title>
              <List
                dataSource={p.retry_major_issues as Issue[]}
                renderItem={(item, index) => {
                  const analysis = issueAnalysisText(item);
                  const sev = severityVisual(item.severity);
                  const excerpt = issueEssayExcerpt(essayContent, item, editSegmentsForMarks);
                  return (
                    <List.Item>
                      <div
                        style={{
                          width: "100%",
                          padding: "10px 12px",
                          borderRadius: 8,
                          border: "1px solid #f0f0f0",
                        }}
                      >
                      <Space direction="vertical" size={8} style={{ width: "100%" }}>
                        <Space wrap align="center">
                          <Tag style={issueTypeTagStyle}>{issueBadgeText(item)}</Tag>
                          {item.severity ? (
                            <Tag style={sev.style}>{severityLabel(item.severity)}</Tag>
                          ) : null}
                        </Space>
                        <Typography.Paragraph style={{ marginBottom: 0 }}>{analysis}</Typography.Paragraph>
                        {excerpt ? (
                          <ReportEssayExcerpt excerpt={excerpt.text} highlightRanges={excerpt.ranges} />
                        ) : null}
                      </Space>
                      </div>
                    </List.Item>
                  );
                }}
              />
            </>
          ) : null}
          <Typography.Title level={5} style={{ marginTop: 16 }}>
            AI 建议
          </Typography.Title>
          <List
            dataSource={(p.suggestions as string[]) ?? []}
            locale={{
              emptyText:
                isSecondPass && p.retry_issue_policy_ok !== false
                  ? "本轮无新增建议；可参考总评摘录与各维度得分。"
                  : "暂无数据",
            }}
            renderItem={(s, i) => (
              <List.Item>
                {i + 1}. {formatSuggestionLine(s)}
              </List.Item>
            )}
          />
          {retrySubmitAllowed ? (
            <Button
              type="primary"
              block
              style={{ marginTop: 16 }}
              onClick={() => navigate(`/reports/${reportId}/retry`)}
            >
              重新作答
            </Button>
          ) : (
            <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
              {String(p.retry_limit_message ?? "").trim() ||
                (firstPassTierLabel
                  ? `本篇已使用完重新批改次数（首稿为${firstPassTierLabel}，最多 ${retryMaxCount} 次，已用 ${retryUsedCount} 次）。`
                  : `本篇已使用完重新批改次数（最多 ${retryMaxCount} 次，已用 ${retryUsedCount} 次）。`)}
            </Typography.Paragraph>
          )}
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
