import { Alert, Button, Col, List, Row, Space, Spin, Tag, Typography, message } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef } from "react";
import { api } from "../api/client";
import { formatApiErrorMessage, showApiError } from "../api/errors";
import EssayHighlightView, { EDIT_FRAGMENT_MARK_STYLE, SegmentIndexLabel } from "./EssayHighlightView";
import KeepSegmentReason from "./KeepSegmentReason";
import { alignTextToLineLayout } from "../utils/essayMarkdownBlocks";
import {
  findKeepRanges,
  segmentRangesWithIndex,
  segmentSourceRangesWithIndex,
  spansToRanges,
  trimRangesToMaxCoverage,
  type KeepSegment,
  type TextSpan,
} from "../utils/highlightEssay";

type KeepSegmentRow = KeepSegment & {
  rubric_dimension_id?: string;
  rubric_dimension_label?: string;
  rubric_standard_note?: string;
  keep_problem?: string;
  keep_solution?: string;
};

type RewriteDemo = {
  status?: string;
  rewrite_text?: string;
  keep_segments?: KeepSegment[];
  edit_segments?: KeepSegment[];
  keep_spans?: TextSpan[];
  edit_spans?: TextSpan[];
  change_summary?: string[];
  minimal_edit_warning?: string | null;
  generated_at?: string;
  validation_check?: {
    passed?: boolean;
    issues_addressed?: boolean;
    errors?: string[];
    warnings?: string[];
    regenerate_attempt?: number;
    issue_fix_status?: {
      tag?: string;
      explanation?: string;
      user_quote?: string;
      fixed?: boolean;
      edit_indexes?: number[];
    }[];
  };
  regenerate_attempt?: number;
};

type Props = {
  reportId: string;
  essayContent: string;
  rewriteDemo?: RewriteDemo | null;
  displayReferenceOnly?: boolean;
  /** 重作后仅针对「待继续改进」生成全文对照 */
  scope?: "first_pass" | "retry_major";
  onPayloadUpdate?: (payload: Record<string, unknown>) => void;
};

export default function ReportRewriteDemo({
  reportId,
  essayContent,
  rewriteDemo,
  displayReferenceOnly,
  scope = "first_pass",
  onPayloadUpdate,
}: Props) {
  const retryMajorScope = scope === "retry_major";
  const qc = useQueryClient();
  const ready = rewriteDemo?.status === "ready" && Boolean(rewriteDemo.rewrite_text?.trim());

  const generate = useMutation({
    mutationFn: (regenerate: boolean) =>
      api<{ rewrite_demo: RewriteDemo; payload: Record<string, unknown> }>(
        `/reports/${reportId}/rewrite-demo${regenerate ? "?regenerate=true" : ""}`,
        { method: "POST" },
      ),
    onSuccess: (res, regenerate) => {
      onPayloadUpdate?.(res.payload);
      qc.setQueryData(["report", reportId], (prev: { id: string; payload: Record<string, unknown> } | undefined) =>
        prev ? { ...prev, payload: res.payload } : prev,
      );
      if (res.rewrite_demo?.validation_check?.passed) {
        message.success(regenerate ? "改写范例已重新生成并通过校验" : "改写范例已生成并通过一致性校验");
      } else if (regenerate) {
        message.warning("已重新生成改写范例，部分校验未通过，请查看下方提示");
      } else {
        message.info("改写范例已生成，请查看下方校验提示");
      }
    },
    onError: (e) => showApiError(e, "改写范例生成失败"),
  });

  const rewriteText = rewriteDemo?.rewrite_text ?? "";
  const alignedRewriteText = useMemo(
    () => (rewriteText ? alignTextToLineLayout(essayContent, rewriteText) : ""),
    [essayContent, rewriteText],
  );

  const keepRanges = trimRangesToMaxCoverage(
    essayContent,
    rewriteDemo?.keep_spans?.length
      ? spansToRanges(essayContent, rewriteDemo.keep_spans)
      : findKeepRanges(essayContent, rewriteDemo?.keep_segments ?? []),
    0.5,
  );
  const keepRows = (rewriteDemo?.keep_segments ?? []) as KeepSegmentRow[];

  const editSegments = rewriteDemo?.edit_segments ?? [];
  const editRanges = trimRangesToMaxCoverage(
    alignedRewriteText,
    segmentRangesWithIndex(alignedRewriteText, editSegments),
    0.55,
  );

  const sourceEditRanges = trimRangesToMaxCoverage(
    essayContent,
    segmentSourceRangesWithIndex(essayContent, editSegments, alignedRewriteText),
    0.55,
  );
  const leftUsePairedEdits = sourceEditRanges.length > 0 && editRanges.length > 0;
  const leftPanelRanges = leftUsePairedEdits ? sourceEditRanges : keepRanges;
  const leftScrollRef = useRef<HTMLDivElement>(null);
  const rightScrollRef = useRef<HTMLDivElement>(null);
  const scrollLock = useRef(false);

  const syncPanelScroll = (source: "left" | "right") => {
    if (scrollLock.current) return;
    scrollLock.current = true;
    const from = source === "left" ? leftScrollRef.current : rightScrollRef.current;
    const to = source === "left" ? rightScrollRef.current : leftScrollRef.current;
    if (from && to) {
      to.scrollTop = from.scrollTop;
    }
    requestAnimationFrame(() => {
      scrollLock.current = false;
    });
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
        {retryMajorScope ? (
          <>
            重作后仅针对<strong>待继续改进（中等及以上）</strong>生成对照：右侧<strong style={{ color: "#cf1322" }}>红底</strong>
            为与每条待改进问题一一对应的局部改写，请按需生成。
          </>
        ) : leftUsePairedEdits ? (
          <>
            左右<strong>同序号</strong>对照：左侧<strong style={{ color: "#d48806" }}>橙底</strong>为待改原文，右侧
            <strong style={{ color: "#cf1322" }}>红底</strong>为对应改写；亮点句见下方「继续保持」列表。
          </>
        ) : (
          <>
            左侧<strong style={{ color: "#389e0d" }}>绿色</strong>为值得保留的亮点句；右侧<strong style={{ color: "#cf1322" }}>红底</strong>
            为局部改写处，序号与下方说明一一对应。
          </>
        )}
      </Typography.Paragraph>

      {displayReferenceOnly ? (
        <Alert type="warning" showIcon message="本次为参考模式，不提供改写范例。" />
      ) : !ready ? (
        <Button type="primary" loading={generate.isPending} onClick={() => generate.mutate(false)}>
          {retryMajorScope ? "生成待继续改进改写对照" : "生成改写范例"}
        </Button>
      ) : null}

      {ready && !displayReferenceOnly ? (
        <Button loading={generate.isPending} onClick={() => generate.mutate(true)}>
          重新生成
        </Button>
      ) : null}

      {generate.isError ? (
        <Alert
          type="error"
          showIcon
          message="生成失败"
          description={formatApiErrorMessage(generate.error, "改写范例生成失败")}
        />
      ) : null}

      {generate.isPending ? (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin tip={ready ? "正在按主要问题重新撰写局部改写…" : "正在根据批改建议撰写范例…"} />
        </div>
      ) : null}

      {ready ? (
        <>
          {rewriteDemo?.minimal_edit_warning ? (
            <Alert type="warning" showIcon message={rewriteDemo.minimal_edit_warning} />
          ) : null}
          {rewriteDemo?.validation_check?.issues_addressed === false ? (
            <Alert
              type="error"
              showIcon
              message="局部改写尚未覆盖全部主要问题"
              description="请点「重新生成」；红标修改须落在评分指出的原文片段上，并真正改写该处表述。"
            />
          ) : null}
          {rewriteDemo?.validation_check?.passed ? (
            <Alert
              type="success"
              showIcon
              message="改写范例已通过一致性校验"
              description={
                (rewriteDemo.validation_check.warnings ?? []).join("；") || undefined
              }
            />
          ) : rewriteDemo?.validation_check?.errors?.length ? (
            <Alert
              type="warning"
              showIcon
              message="改写范例校验提示"
              description={rewriteDemo.validation_check.errors.join("；")}
            />
          ) : null}
          {(rewriteDemo?.validation_check?.issue_fix_status?.length ?? 0) > 0 ? (
            <div>
              <Typography.Text strong>主要问题 → 局部改写落实</Typography.Text>
              <List
                size="small"
                style={{ marginTop: 8 }}
                split={false}
                dataSource={rewriteDemo?.validation_check?.issue_fix_status ?? []}
                renderItem={(row) => (
                  <List.Item style={{ display: "block", padding: "0 0 10px" }}>
                    <div
                      style={{
                        padding: "10px 12px",
                        borderRadius: 8,
                        border: `1px solid ${row.fixed ? "#b7eb8f" : "#ffa39e"}`,
                        background: row.fixed ? "#f6ffed" : "#fff2f0",
                      }}
                    >
                      <Space wrap style={{ marginBottom: 6 }}>
                        <Tag color={row.fixed ? "success" : "error"}>{row.fixed ? "已改写" : "未落实"}</Tag>
                        {row.tag ? <Tag>{row.tag}</Tag> : null}
                        {(row.edit_indexes ?? []).length > 0 ? (
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            对应修改序号：{(row.edit_indexes ?? []).join("、")}
                          </Typography.Text>
                        ) : null}
                      </Space>
                      {row.explanation ? (
                        <Typography.Paragraph style={{ marginBottom: 6 }}>{row.explanation}</Typography.Paragraph>
                      ) : null}
                      {row.user_quote ? (
                        <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                          原文：「{row.user_quote.length > 100 ? `${row.user_quote.slice(0, 48)}……${row.user_quote.slice(-48)}` : row.user_quote}」
                        </Typography.Text>
                      ) : null}
                    </div>
                  </List.Item>
                )}
              />
            </div>
          ) : null}
          {(rewriteDemo?.change_summary?.length ?? 0) > 0 ? (
            <div>
              <Typography.Text strong>相对原文的主要改动</Typography.Text>
              <List
                size="small"
                style={{ marginTop: 8 }}
                dataSource={rewriteDemo?.change_summary ?? []}
                renderItem={(line) => <List.Item>{line}</List.Item>}
              />
            </div>
          ) : null}

          <Row gutter={16} align="stretch" style={{ alignItems: "stretch" }}>
            <Col xs={24} lg={12} style={{ display: "flex", flexDirection: "column" }}>
              <Typography.Text strong>
                {leftUsePairedEdits
                  ? "你的作答（待改原文 · 序号与右侧一致）"
                  : "你的作答（标准亮点句 · 绿色标注）"}
              </Typography.Text>
              <EssayHighlightView
                content={essayContent}
                ranges={leftPanelRanges}
                highlightBg={leftUsePairedEdits ? "#ffd591" : "#d9f7be"}
                highlightTitle={leftUsePairedEdits ? "待改原文" : "符合标准，继续保持"}
                showSegmentIndex={leftUsePairedEdits}
                preserveOriginalLayout
                panelBg="#fff"
                borderColor={leftUsePairedEdits ? "#ffc069" : "#b7eb8f"}
                panelMinHeight={420}
                panelRef={leftScrollRef}
                onPanelScroll={() => syncPanelScroll("left")}
              />
            </Col>
            <Col xs={24} lg={12} style={{ display: "flex", flexDirection: "column" }}>
              <Typography.Text strong>局部改写范例（改动处标红）</Typography.Text>
              <EssayHighlightView
                content={alignedRewriteText}
                ranges={editRanges}
                highlightBg="#ffa39e"
                highlightTitle="相对原文修改"
                showSegmentIndex
                preserveOriginalLayout
                panelBg="#fff"
                borderColor="#ffa39e"
                panelMinHeight={420}
                panelRef={rightScrollRef}
                onPanelScroll={() => syncPanelScroll("right")}
              />
            </Col>
          </Row>

          {editSegments.length > 0 ? (
            <div>
              <Typography.Text strong>修改片段说明</Typography.Text>
              <List
                size="small"
                style={{ marginTop: 8 }}
                split={false}
                dataSource={editSegments}
                renderItem={(row, index) => {
                  const segmentIndex = index + 1;
                  return (
                    <List.Item style={{ display: "block", padding: "0 0 10px" }}>
                      <div
                        style={{
                          padding: "10px 12px",
                          borderRadius: 8,
                          border: "1px solid #f0f0f0",
                          background: "#fafafa",
                        }}
                      >
                        <Typography.Paragraph
                          style={{ marginBottom: row.reason ? 6 : 0, lineHeight: 1.85 }}
                        >
                          <SegmentIndexLabel index={segmentIndex} />
                          <mark style={EDIT_FRAGMENT_MARK_STYLE}>{row.quote}</mark>
                        </Typography.Paragraph>
                        {(row as { issue_tag?: string }).issue_tag ? (
                          <Tag color="volcano" style={{ marginBottom: 4 }}>
                            {(row as { issue_tag?: string }).issue_tag}
                          </Tag>
                        ) : null}
                        {row.reason ? (
                          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                            {row.reason}
                          </Typography.Text>
                        ) : null}
                      </div>
                    </List.Item>
                  );
                }}
              />
            </div>
          ) : null}

          {keepRows.length > 0 ? (
            <div>
              <Typography.Text strong>继续保持的写法</Typography.Text>
              <List
                style={{ marginTop: 8 }}
                size="small"
                dataSource={keepRows}
                renderItem={(row) => (
                  <List.Item>
                    <Space direction="vertical" size={4} style={{ width: "100%" }}>
                      {row.rubric_dimension_label ? (
                        <Tag color="green">{row.rubric_dimension_label}</Tag>
                      ) : null}
                      <Typography.Text style={{ color: "#389e0d" }}>「{row.quote}」</Typography.Text>
                      {row.reason ? (
                        <KeepSegmentReason
                          reason={row.reason}
                          keepProblem={row.keep_problem}
                          keepSolution={row.keep_solution}
                          solutionFallback={row.rubric_standard_note}
                        />
                      ) : null}
                    </Space>
                  </List.Item>
                )}
              />
            </div>
          ) : null}

        </>
      ) : null}
    </Space>
  );
}
