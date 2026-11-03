import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { showApiError } from "../../api/errors";
import {
  LEVEL_HINT,
  LEVEL_LABELS,
  TRAIT_HINT,
  TRAIT_LABELS,
  formatQuestionLabel,
  levelSelectLabel,
  traitSelectLabel,
} from "../../utils/traitLabels";

type AnchorListRow = {
  id: string;
  question_id: string;
  title: string;
  aggregate_level: string;
  content_preview: string;
};

type ReviewRow = {
  id: string;
  reviewer_label: string;
  trait_id: string;
  level: string;
  evidence_positive: string[];
  reviewer_rationale: string;
  dispute_note: string;
  created_at: string | null;
};

type AnchorDetail = {
  id: string;
  question_id: string;
  title: string;
  content: string;
  aggregate_level: string;
  trait_levels: Record<string, string>;
  reviews: ReviewRow[];
};

const TRAIT_IDS = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"] as const;
const LEVELS = ["L0", "L1", "L2", "L3", "L4"] as const;

function formatReviewTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("zh-CN", { hour12: false });
}

export default function AdminAnchorAnnotationPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const anchorId = searchParams.get("id") ?? undefined;
  const [form] = Form.useForm();

  const { data: anchors } = useQuery({
    queryKey: ["admin-anchor-essays-all"],
    queryFn: () => api<AnchorListRow[]>("/admin/anchor-essays"),
  });

  const {
    data: detail,
    refetch: refetchDetail,
    isLoading: detailLoading,
  } = useQuery({
    queryKey: ["admin-anchor-detail", anchorId],
    queryFn: () => api<AnchorDetail>(`/admin/anchor-essays/${anchorId}`),
    enabled: !!anchorId,
  });

  const selectedTraitIds = Form.useWatch("trait_ids", form) as string[] | undefined;
  const [deletingReviewId, setDeletingReviewId] = useState<string | null>(null);

  const submitReview = useMutation({
    mutationFn: (body: {
      reviewer_label: string;
      level: string;
      dispute_note: string;
      items: { trait_id: string; evidence_positive: string[]; reviewer_rationale: string }[];
    }) =>
      api(`/admin/anchor-essays/${anchorId}/reviews/batch`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (_data, variables) => {
      message.success(`已保存 ${variables.items.length} 个维度的标注`);
      const resetEvidence: Record<string, string> = {};
      const resetRationale: Record<string, string> = {};
      for (const tid of variables.items.map((i) => i.trait_id)) {
        resetEvidence[tid] = "";
        resetRationale[tid] = "";
      }
      form.setFieldsValue({ evidence_by_trait: resetEvidence, rationale_by_trait: resetRationale });
      form.resetFields(["dispute_note"]);
      refetchDetail();
    },
    onError: showApiError,
  });

  const deleteReview = useMutation({
    mutationFn: (reviewId: string) =>
      api(`/admin/anchor-essays/${anchorId}/reviews/${reviewId}`, { method: "DELETE" }),
    onSuccess: () => {
      message.success("已删除该条标注");
      refetchDetail();
    },
    onError: showApiError,
    onSettled: () => setDeletingReviewId(null),
  });

  const reviewColumns = useMemo(
    () => [
      { title: "评者姓名", dataIndex: "reviewer_label", width: 100 },
      {
        title: "维度",
        dataIndex: "trait_id",
        width: 160,
        render: (tid: string) => traitSelectLabel(tid),
      },
      {
        title: "档位",
        dataIndex: "level",
        width: 120,
        render: (lv: string) => levelSelectLabel(lv),
      },
      {
        title: "正向证据",
        dataIndex: "evidence_positive",
        render: (v: string[]) => (v?.length ? v.join("；") : "—"),
      },
      {
        title: "评者解析",
        dataIndex: "reviewer_rationale",
        ellipsis: true,
        render: (v: string) => (v?.trim() ? v : "—"),
      },
      { title: "争议说明", dataIndex: "dispute_note", ellipsis: true },
      {
        title: "时间",
        dataIndex: "created_at",
        width: 168,
        render: (t: string | null) => formatReviewTime(t),
      },
      {
        title: "操作",
        key: "actions",
        width: 72,
        fixed: "right" as const,
        render: (_: unknown, row: ReviewRow) => (
          <Popconfirm
            title="删除这条标注？"
            description="删除后不可恢复。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => {
              setDeletingReviewId(row.id);
              deleteReview.mutate(row.id);
            }}
          >
            <Button
              type="link"
              size="small"
              danger
              loading={deletingReviewId === row.id && deleteReview.isPending}
            >
              删除
            </Button>
          </Popconfirm>
        ),
      },
    ],
    [deleteReview, deletingReviewId],
  );

  const aggregateLabel = detail?.aggregate_level
    ? levelSelectLabel(detail.aggregate_level)
    : "—";

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        锚作文维度标注
      </Typography.Title>
      <Alert
        type="info"
        showIcon
        message="锚作文是某题下的「标尺范文」：新作文会与锚对比定相对水平。"
        description={
          <>
            {TRAIT_HINT} {LEVEL_HINT} 多位评者可分别提交，系统不要求完全一致。先在{" "}
            <Link to="/admin/anchors">锚作文管理</Link> 录入正文，再在此标注。
          </>
        }
      />

      <Card size="small" title="选择锚作文">
        <Select
          showSearch
          placeholder="请选择要标注的锚作文名称"
          style={{ width: "100%", maxWidth: 560 }}
          value={anchorId}
          optionFilterProp="label"
          onChange={(id) => setSearchParams(id ? { id } : {})}
          options={(anchors ?? []).map((a) => {
            const title = (a.title || "未命名锚作文").trim();
            const agg = a.aggregate_level ? levelSelectLabel(a.aggregate_level) : "";
            return {
              value: a.id,
              label: agg ? `${title}（${agg}）` : title,
            };
          })}
        />
      </Card>

      {anchorId && detailLoading ? (
        <Typography.Text type="secondary">加载中…</Typography.Text>
      ) : null}

      {detail ? (
        <>
          <Card size="small" title={detail.title?.trim() || "锚作文正文"}>
            <Typography.Paragraph
              style={{
                whiteSpace: "pre-wrap",
                maxHeight: 280,
                overflow: "auto",
                marginBottom: 8,
                fontSize: 13,
              }}
            >
              {detail.content}
            </Typography.Paragraph>
            <Space wrap>
              <Tag>题目：{formatQuestionLabel(detail.question_id)}</Tag>
              <Tag color="blue">综合水平：{aggregateLabel}</Tag>
              {TRAIT_IDS.map((t) => (
                <Tag key={t}>
                  {TRAIT_LABELS[t]}：
                  {detail.trait_levels?.[t]
                    ? levelSelectLabel(detail.trait_levels[t])
                    : "未标注"}
                </Tag>
              ))}
            </Space>
          </Card>

          <Card size="small" title="提交本评者标注">
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                level: "L2",
                trait_ids: ["T1"],
                evidence_by_trait: {},
                rationale_by_trait: {},
              }}
              onFinish={(v) => {
                const traitIds = (Array.isArray(v.trait_ids) ? v.trait_ids : [v.trait_ids]).filter(
                  Boolean,
                ) as string[];
                if (traitIds.length === 0) {
                  message.warning("请至少选择一个维度");
                  return;
                }
                const byTrait = (v.evidence_by_trait ?? {}) as Record<string, string>;
                const rationaleByTrait = (v.rationale_by_trait ?? {}) as Record<string, string>;
                const items = traitIds.map((tid) => {
                  const block = String(byTrait[tid] ?? "");
                  const evidence_positive = block
                    .split("\n")
                    .map((s) => s.trim())
                    .filter(Boolean);
                  const reviewer_rationale = String(rationaleByTrait[tid] ?? "").trim();
                  return { trait_id: tid, evidence_positive, reviewer_rationale };
                });
                submitReview.mutate({
                  reviewer_label: String(v.reviewer_label ?? "").trim(),
                  level: v.level,
                  dispute_note: v.dispute_note ?? "",
                  items,
                });
              }}
            >
              <Space wrap style={{ width: "100%" }} align="start">
                <Form.Item
                  name="reviewer_label"
                  label="评者姓名"
                  rules={[{ required: true, message: "请填写您的姓名或工号" }]}
                  extra="用于区分不同评者，请填真实姓名（勿用 reviewer_1 等占位符）。"
                >
                  <Input style={{ width: 160 }} placeholder="例如：张老师" />
                </Form.Item>
                <Form.Item
                  name="trait_ids"
                  label="维度（可多选）"
                  rules={[{ required: true, message: "请至少选择一个维度" }]}
                  tooltip={TRAIT_HINT}
                  extra="一次提交共用同一档位；若各维度档位不同，请分多次提交。"
                >
                  <Select
                    mode="multiple"
                    style={{ width: "100%", maxWidth: 520 }}
                    placeholder="选择要标注的维度"
                    options={TRAIT_IDS.map((t) => ({ value: t, label: traitSelectLabel(t) }))}
                  />
                </Form.Item>
                <Form.Item
                  name="level"
                  label="档位"
                  rules={[{ required: true }]}
                  tooltip={LEVEL_HINT}
                >
                  <Select
                    style={{ width: 160 }}
                    options={LEVELS.map((l) => ({ value: l, label: levelSelectLabel(l) }))}
                  />
                </Form.Item>
              </Space>
              {(selectedTraitIds ?? []).length > 0 ? (
                <>
                  <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
                    每个维度：正向证据须摘自上方正文（每行一条）；评者解析为可选判档说明（可留空）。
                  </Typography.Text>
                  {(selectedTraitIds ?? []).map((tid) => (
                    <div key={tid}>
                      <Form.Item
                        name={["evidence_by_trait", tid]}
                        label={`${TRAIT_LABELS[tid] ?? tid} · 正向证据`}
                      >
                        <Input.TextArea
                          rows={2}
                          placeholder={`从正文摘录支持「${TRAIT_LABELS[tid] ?? tid}」的原句…`}
                        />
                      </Form.Item>
                      <Form.Item
                        name={["rationale_by_trait", tid]}
                        label={`${TRAIT_LABELS[tid] ?? tid} · 评者解析（可选）`}
                      >
                        <Input.TextArea
                          rows={2}
                          placeholder="简要说明为何给出该档位，供其他评者参考…"
                        />
                      </Form.Item>
                    </div>
                  ))}
                </>
              ) : null}
              <Form.Item name="dispute_note" label="争议说明（可选）">
                <Input.TextArea rows={2} placeholder="若与其他评者档位不同，可简述理由…" />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={submitReview.isPending}>
                保存标注
              </Button>
            </Form>
          </Card>

          <Card size="small" title={`历史标注（${detail.reviews.length} 条）`}>
            <Table
              size="small"
              rowKey="id"
              pagination={{ pageSize: 8 }}
              columns={reviewColumns}
              dataSource={detail.reviews}
            />
          </Card>
        </>
      ) : null}
    </Space>
  );
}
