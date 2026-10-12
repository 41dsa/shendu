import { Alert, Button, Col, List, Row, Space, Spin, Tag, Typography } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import EssayHighlightView, { SegmentIndexLabel } from "./EssayHighlightView";
import KeepSegmentReason from "./KeepSegmentReason";
import {
  findKeepRanges,
  segmentRangesWithIndex,
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
};

type Props = {
  reportId: string;
  essayContent: string;
  rewriteDemo?: RewriteDemo | null;
  displayReferenceOnly?: boolean;
  onPayloadUpdate?: (payload: Record<string, unknown>) => void;
};

export default function ReportRewriteDemo({
  reportId,
  essayContent,
  rewriteDemo,
  displayReferenceOnly,
  onPayloadUpdate,
}: Props) {
  const qc = useQueryClient();
  const ready = rewriteDemo?.status === "ready" && Boolean(rewriteDemo.rewrite_text?.trim());

  const generate = useMutation({
    mutationFn: () =>
      api<{ rewrite_demo: RewriteDemo; payload: Record<string, unknown> }>(
        `/reports/${reportId}/rewrite-demo`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      onPayloadUpdate?.(res.payload);
      qc.setQueryData(["report", reportId], (prev: { id: string; payload: Record<string, unknown> } | undefined) =>
        prev ? { ...prev, payload: res.payload } : prev,
      );
    },
  });

  const rewriteText = rewriteDemo?.rewrite_text ?? "";
  const keepRanges = trimRangesToMaxCoverage(
    essayContent,
    rewriteDemo?.keep_spans?.length
      ? spansToRanges(essayContent, rewriteDemo.keep_spans)
      : findKeepRanges(essayContent, rewriteDemo?.keep_segments ?? []),
    0.5,
  );
  const keepRows = (rewriteDemo?.keep_segments ?? []) as KeepSegmentRow[];

  const editSegments = rewriteDemo?.edit_segments ?? [];
  const editRanges = trimRangesToMaxCoverage(rewriteText, segmentRangesWithIndex(rewriteText, editSegments));

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
        左侧<strong style={{ color: "#389e0d" }}>绿色</strong>为值得保留的亮点句；右侧<strong style={{ color: "#cf1322" }}>淡红</strong>
        为局部改写处，序号与下方说明一一对应。
      </Typography.Paragraph>

      {displayReferenceOnly ? (
        <Alert type="warning" showIcon message="本次为参考模式，不提供改写范例。" />
      ) : !ready ? (
        <Button type="primary" loading={generate.isPending} onClick={() => generate.mutate()}>
          生成改写范例
        </Button>
      ) : null}

      {generate.isError ? (
        <Alert type="error" showIcon message="生成失败" description={String(generate.error)} />
      ) : null}

      {generate.isPending && !ready ? (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin tip="正在根据批改建议撰写范例…" />
        </div>
      ) : null}

      {ready ? (
        <>
          {rewriteDemo?.minimal_edit_warning ? (
            <Alert type="warning" showIcon message={rewriteDemo.minimal_edit_warning} />
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

          <Row gutter={16} align="top">
            <Col xs={24} lg={12}>
              <Typography.Text strong>你的作答（标准亮点句 · 绿色标注）</Typography.Text>
              <EssayHighlightView
                content={essayContent}
                ranges={keepRanges}
                highlightBg="#d9f7be"
                highlightTitle="符合标准，继续保持"
                emptyLabel="暂无作答正文"
              />
            </Col>
            <Col xs={24} lg={12}>
              <Typography.Text strong>局部改写范例（改动处标红）</Typography.Text>
              <EssayHighlightView
                content={rewriteText}
                ranges={editRanges}
                highlightBg="#fff1f0"
                highlightTitle="相对原文修改"
                showSegmentIndex
                panelBg="#fafafa"
                borderColor="#f0f0f0"
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
                          display: "flex",
                          gap: 10,
                          alignItems: "flex-start",
                          padding: "10px 12px",
                          borderRadius: 8,
                          border: "1px solid #f0f0f0",
                          background: "#fafafa",
                        }}
                      >
                        <span style={{ flexShrink: 0, lineHeight: "22px" }}>
                          <SegmentIndexLabel index={segmentIndex} />
                        </span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <Typography.Paragraph style={{ marginBottom: row.reason ? 6 : 0, color: "rgba(0,0,0,0.88)" }}>
                            {row.quote}
                          </Typography.Paragraph>
                          {row.reason ? (
                            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                              {row.reason}
                            </Typography.Text>
                          ) : null}
                        </div>
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

          <Button size="small" loading={generate.isPending} onClick={() => generate.mutate()}>
            重新生成
          </Button>
        </>
      ) : null}
    </Space>
  );
}
