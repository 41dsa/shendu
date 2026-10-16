import { Alert, Button, List, Space, Spin, Tag, Typography, message } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { api } from "../api/client";
import { formatApiErrorMessage, showApiError } from "../api/errors";
import EssayHighlightView, { SegmentIndexLabel } from "./EssayHighlightView";
import { segmentRangesWithIndex } from "../utils/highlightEssay";

type BodyThesis = {
  index?: number;
  title?: string;
};

type MarkSegment = {
  quote?: string;
  point_label?: string;
  thesis_index?: number;
  /** @deprecated v2 逐条分论点，请重新生成 */
  sub_thesis?: string;
  why?: string;
};

type ReferenceSample = {
  status?: string;
  schema_version?: number;
  sample_text?: string;
  target_tier_note?: string;
  target_score_band?: number[];
  body_theses?: BodyThesis[];
  mark_segments?: MarkSegment[];
  generated_at?: string;
};

type Props = {
  reportId: string;
  referenceSample?: ReferenceSample | null;
  displayReferenceOnly?: boolean;
  onPayloadUpdate?: (payload: Record<string, unknown>) => void;
};

function thesisTitleMap(theses: BodyThesis[]): Map<number, string> {
  const m = new Map<number, string>();
  for (const t of theses) {
    const idx = Number(t.index);
    const title = String(t.title ?? "").trim();
    if (idx >= 1 && title) m.set(idx, title);
  }
  return m;
}

export default function ReportReferenceSample({
  reportId,
  referenceSample,
  displayReferenceOnly,
  onPayloadUpdate,
}: Props) {
  const qc = useQueryClient();
  const ready = referenceSample?.status === "ready" && Boolean(referenceSample.sample_text?.trim());
  const schemaOk = (referenceSample?.schema_version ?? 0) >= 6;
  const scoreVerified = Boolean(
    (referenceSample as { score_verification?: { engine_total?: number } })?.score_verification
      ?.engine_total,
  );
  const thesisAnchors = (
    referenceSample as {
      thesis_anchors?: {
        start: number;
        thesis_index: number;
        title: string;
        lead_start?: number;
        lead_end?: number;
      }[];
    }
  )?.thesis_anchors;
  const bodyTheses = (referenceSample?.body_theses ?? []).filter(
    (t) => t.title && Number(t.index) >= 1,
  );
  const thesisByIndex = useMemo(() => thesisTitleMap(bodyTheses), [bodyTheses]);

  const generate = useMutation({
    mutationFn: (regenerate: boolean) =>
      api<{ reference_sample: ReferenceSample; payload: Record<string, unknown> }>(
        `/reports/${reportId}/reference-sample${regenerate ? "?regenerate=true" : ""}`,
        { method: "POST" },
      ),
    onSuccess: (res, regenerate) => {
      onPayloadUpdate?.(res.payload);
      qc.setQueryData(["report", reportId], (prev: { id: string; payload: Record<string, unknown> } | undefined) =>
        prev ? { ...prev, payload: res.payload } : prev,
      );
      message.success(regenerate ? "参考范文已重新生成" : "参考范文已生成");
    },
    onError: (e) => showApiError(e, "参考范文生成失败"),
  });

  const sampleText = referenceSample?.sample_text ?? "";
  const markSegments = referenceSample?.mark_segments ?? [];

  const highlightRanges = useMemo(() => {
    const leadRanges = (thesisAnchors ?? [])
      .filter((a) => (a.lead_end ?? 0) > (a.lead_start ?? a.start))
      .map((a) => ({
        start: a.lead_start ?? a.start,
        end: a.lead_end ?? a.start,
        reason: `分论点${a.thesis_index}段旨（正文首句）`,
        variant: "thesis_lead" as const,
      }));
    const markRanges = segmentRangesWithIndex(
      sampleText,
      markSegments.map((seg) => ({
        quote: seg.quote ?? "",
        reason: [seg.point_label, seg.why].filter(Boolean).join("："),
      })),
    ).map((r) => ({ ...r, variant: "mark" as const }));
    return [...leadRanges, ...markRanges].sort((a, b) => a.start - b.start);
  }, [sampleText, markSegments, thesisAnchors]);

  if (displayReferenceOnly) {
    return <Alert type="warning" showIcon message="参考模式下不提供 AI 参考范文。" />;
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0, fontSize: 13 }}>
        根据本题<strong>作答要求</strong>与<strong>给定材料</strong>生成的示范稿（二类中上）。
        {scoreVerified ? "已通过与本题相同的评分引擎抽检，抄交批改应不低于目标档位下沿。" : "重新生成后将经评分引擎档位抽检。"}
        上方为提纲；正文<strong>蓝底加粗</strong>为各段分论点首句，<strong>橙底序号</strong>为段内采分点。
      </Typography.Paragraph>

      {ready && !schemaOk ? (
        <Alert
          type="warning"
          showIcon
          message="参考范文格式已更新"
          description="请点击「重新生成参考范文」：新版含评分引擎档位抽检，分论点须写在段首并在正文标注。"
        />
      ) : null}

      {!ready ? (
        <Button type="primary" loading={generate.isPending} onClick={() => generate.mutate(false)}>
          我是懦夫，我要模版
        </Button>
      ) : (
        <Button loading={generate.isPending} onClick={() => generate.mutate(true)}>
          重新生成参考范文
        </Button>
      )}

      {generate.isError ? (
        <Alert
          type="error"
          showIcon
          message="无法提供参考范例"
          description={formatApiErrorMessage(
            generate.error,
            "参考范例未通过评分引擎分数档位（二类中上）抽检，不再提供低分模版",
          )}
        />
      ) : null}

      {generate.isPending ? (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin tip="正在根据材料与作答要求撰写参考范文…" />
        </div>
      ) : null}

      {ready ? (
        <>
          {referenceSample?.target_tier_note ? (
            <Alert type="info" showIcon message={referenceSample.target_tier_note} />
          ) : null}

          {bodyTheses.length >= 3 ? (
            <div>
              <Typography.Text strong>提纲：全文 {bodyTheses.length} 个分论点（对应正文分段）</Typography.Text>
              <List
                size="small"
                style={{ marginTop: 8 }}
                split={false}
                dataSource={[...bodyTheses].sort((a, b) => Number(a.index) - Number(b.index))}
                renderItem={(row) => (
                  <List.Item style={{ padding: "4px 0" }}>
                    <Space align="start">
                      <Tag color="geekblue">分论点 {row.index}</Tag>
                      <Typography.Text style={{ fontSize: 14, color: "#141414", fontWeight: 600 }}>
                        {row.title}
                      </Typography.Text>
                    </Space>
                  </List.Item>
                )}
              />
            </div>
          ) : null}

          <EssayHighlightView
            content={sampleText}
            ranges={highlightRanges}
            highlightBg="#ffd591"
            highlightTitle="采分点示范"
            showSegmentIndex
            referenceTemplate
            panelBg="#fff"
            borderColor="#ffc069"
            panelMinHeight={360}
          />

          {markSegments.length > 0 ? (
            <div>
              <Typography.Text strong>采分点与写法解析</Typography.Text>
              <Typography.Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 8, fontSize: 12 }}>
                下列为段内写法示范，每条标注所属的第几个分论点。
              </Typography.Paragraph>
              <List
                size="small"
                split={false}
                dataSource={markSegments}
                renderItem={(row, index) => {
                  const ti = Number(row.thesis_index);
                  const thesisTitle = ti > 0 ? thesisByIndex.get(ti) : undefined;
                  const legacyThesis = row.sub_thesis?.trim();
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
                        <Space wrap align="start" style={{ marginBottom: 6 }}>
                          <SegmentIndexLabel index={index + 1} />
                          {row.point_label ? <Tag color="blue">{row.point_label}</Tag> : null}
                          {thesisTitle ? (
                            <Tag color="purple">
                              分论点 {ti}：{thesisTitle.length > 22 ? `${thesisTitle.slice(0, 20)}…` : thesisTitle}
                            </Tag>
                          ) : legacyThesis ? (
                            <Tag color="default">（旧版）{legacyThesis.slice(0, 24)}</Tag>
                          ) : null}
                        </Space>
                        {row.quote ? (
                          <Typography.Paragraph style={{ marginBottom: 6, fontSize: 13 }}>
                            「
                            {row.quote.length > 100
                              ? `${row.quote.slice(0, 48)}…${row.quote.slice(-40)}`
                              : row.quote}
                            」
                          </Typography.Paragraph>
                        ) : null}
                        {row.why ? (
                          <Typography.Paragraph type="secondary" style={{ fontSize: 13, marginBottom: 0 }}>
                            {row.why}
                          </Typography.Paragraph>
                        ) : null}
                      </div>
                    </List.Item>
                  );
                }}
              />
            </div>
          ) : null}
        </>
      ) : null}
    </Space>
  );
}
