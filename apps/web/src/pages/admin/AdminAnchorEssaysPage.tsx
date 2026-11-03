import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { showApiError } from "../../api/errors";
import {
  TRAIT_LABELS,
  formatQuestionLabel,
  formatTraitLevelsCompact,
  levelSelectLabel,
} from "../../utils/traitLabels";

type QRow = { id: string; title: string };

type AnchorRow = {
  id: string;
  question_id: string;
  title: string;
  aggregate_level: string;
  trait_levels: Record<string, string>;
  is_published: boolean;
  content_preview: string;
  created_at: string | null;
};

type SummaryRow = {
  question_id: string;
  question_title: string;
  published_count: number;
  total_count: number;
  relative_scale_ready: boolean;
  center_score_ready: boolean;
  in_target_band: boolean;
  target_band_min: number;
  target_band_max: number;
};

const TRAIT_IDS = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"] as const;
const LEVELS = ["L0", "L1", "L2", "L3", "L4"] as const;

function defaultTraitLevels(aggregate: string): Record<string, string> {
  const lv = aggregate || "L2";
  return Object.fromEntries(TRAIT_IDS.map((t) => [t, lv]));
}

export default function AdminAnchorEssaysPage() {
  const [filterQuestionId, setFilterQuestionId] = useState<string | undefined>();
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: questions } = useQuery({
    queryKey: ["admin-questions"],
    queryFn: () => api<QRow[]>("/admin/questions"),
  });

  const { data: summary, refetch: refetchSummary } = useQuery({
    queryKey: ["admin-anchor-summary"],
    queryFn: () => api<SummaryRow[]>("/admin/anchor-essays/summary"),
  });

  const { data: anchorCalibration } = useQuery({
    queryKey: ["admin-anchor-calibration", filterQuestionId],
    queryFn: () =>
      api<{
        pair_count: number;
        ranked_submission_ids: string[];
        overall_strengths: Record<string, number>;
      }>(`/admin/questions/${filterQuestionId}/anchor-calibration`),
    enabled: !!filterQuestionId,
  });

  const { data: anchors, refetch: refetchAnchors } = useQuery({
    queryKey: ["admin-anchor-essays", filterQuestionId],
    queryFn: () =>
      api<AnchorRow[]>(
        filterQuestionId
          ? `/admin/anchor-essays?question_id=${encodeURIComponent(filterQuestionId)}`
          : "/admin/anchor-essays",
      ),
  });

  const qOptions = useMemo(
    () => (questions ?? []).map((q) => ({ value: q.id, label: `${q.title}（${q.id}）` })),
    [questions],
  );

  const createMut = useMutation({
    mutationFn: (v: Record<string, unknown>) =>
      api("/admin/anchor-essays", { method: "POST", body: JSON.stringify(v) }),
    onSuccess: () => {
      message.success("锚作文已创建");
      setCreateOpen(false);
      form.resetFields();
      refetchAnchors();
      refetchSummary();
    },
    onError: showApiError,
  });

  const patchMut = useMutation({
    mutationFn: (v: { id: string; is_published: boolean }) =>
      api(`/admin/anchor-essays/${v.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_published: v.is_published }),
      }),
    onSuccess: () => {
      refetchAnchors();
      refetchSummary();
    },
    onError: showApiError,
  });

  const seedMut = useMutation({
    mutationFn: (questionId: string) =>
      api<{ added: number }>(`/admin/anchor-essays/seed-demo?question_id=${encodeURIComponent(questionId)}`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: (res) => {
      message.success(`已写入 ${res.added} 篇演示锚（L0～L4）`);
      refetchAnchors();
      refetchSummary();
    },
    onError: showApiError,
  });

  const aggregateWatch = Form.useWatch("aggregate_level", form) ?? "L2";

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        message="PRD V1 锚作文（相对尺度）"
        description="已发布锚 ≥3 篇启用最近邻相对尺度；≥10 篇参与 center 档分数展示。运营目标 10～20 篇/题。CLI：python scripts/seed_demo_anchors.py <question_id>。"
      />

      <Card title="按题覆盖统计" size="small">
        <Table
          rowKey="question_id"
          size="small"
          pagination={{ pageSize: 8 }}
          dataSource={summary ?? []}
          locale={{ emptyText: "尚无锚作文，请选题录入或一键演示种子" }}
          columns={[
            { title: "题目", dataIndex: "question_title", ellipsis: true },
            { title: "题号", dataIndex: "question_id", width: 120, ellipsis: true },
            {
              title: "已发布",
              dataIndex: "published_count",
              width: 72,
              render: (n: number, row) => (
                <Tag color={row.in_target_band ? "green" : n >= 3 ? "blue" : "default"}>{n}</Tag>
              ),
            },
            { title: "总数", dataIndex: "total_count", width: 64 },
            {
              title: "相对尺度",
              width: 88,
              render: (_, row) =>
                row.relative_scale_ready ? <Tag color="green">≥3 OK</Tag> : <Tag>待补</Tag>,
            },
            {
              title: "center 分",
              width: 88,
              render: (_, row) =>
                row.center_score_ready ? <Tag color="green">≥10 OK</Tag> : <Tag>待补</Tag>,
            },
            {
              title: "操作",
              width: 200,
              render: (_, row) => (
                <Space size="small">
                  <Button
                    size="small"
                    onClick={() => setFilterQuestionId(row.question_id)}
                  >
                    查看列表
                  </Button>
                  <Button
                    size="small"
                    loading={seedMut.isPending}
                    onClick={() => seedMut.mutate(row.question_id)}
                  >
                    补演示锚
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      {filterQuestionId && anchorCalibration && anchorCalibration.pair_count > 0 ? (
        <Card title="V2 成对比较 · Bradley-Terry 校准" size="small">
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="已完成成对比较">{anchorCalibration.pair_count}</Descriptions.Item>
            <Descriptions.Item label="相对排序（submission）">
              {(anchorCalibration.ranked_submission_ids ?? []).slice(0, 5).join("、") || "—"}
            </Descriptions.Item>
          </Descriptions>
          <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 0 }}>
            训练包：GET /admin/weak-supervision/bundle?question_id={filterQuestionId}
          </Typography.Paragraph>
        </Card>
      ) : null}

      <Card
        title="锚作文列表"
        size="small"
        extra={
          <Space wrap>
            <Select
              allowClear
              placeholder="按题筛选"
              style={{ minWidth: 280 }}
              value={filterQuestionId}
              onChange={(v) => setFilterQuestionId(v)}
              options={qOptions}
            />
            {filterQuestionId && (
              <Button loading={seedMut.isPending} onClick={() => seedMut.mutate(filterQuestionId)}>
                一键 L0～L4 演示
              </Button>
            )}
            <Button type="primary" onClick={() => setCreateOpen(true)}>
              新建锚作文
            </Button>
          </Space>
        }
      >
        <Table
          rowKey="id"
          size="small"
          dataSource={anchors ?? []}
          columns={[
            { title: "锚作文名称", dataIndex: "title", ellipsis: true },
            {
              title: "题目",
              dataIndex: "question_id",
              width: 108,
              ellipsis: true,
              render: (qid: string) => formatQuestionLabel(qid),
            },
            {
              title: "综合档位",
              dataIndex: "aggregate_level",
              width: 100,
              render: (lv: string) => levelSelectLabel(lv),
            },
            {
              title: "发布",
              dataIndex: "is_published",
              width: 72,
              render: (pub: boolean, row) => (
                <Switch
                  checked={pub}
                  loading={patchMut.isPending}
                  onChange={(checked) => patchMut.mutate({ id: row.id, is_published: checked })}
                />
              ),
            },
            { title: "摘要", dataIndex: "content_preview", ellipsis: true },
            {
              title: "各维度档位",
              dataIndex: "trait_levels",
              ellipsis: true,
              render: (lv: Record<string, string>) => (
                <Typography.Text style={{ fontSize: 12 }} title={formatTraitLevelsCompact(lv)}>
                  {formatTraitLevelsCompact(lv)}
                </Typography.Text>
              ),
            },
            {
              title: "标注",
              width: 80,
              render: (_: unknown, row: AnchorRow) => (
                <Link to={`/admin/anchor-annotation?id=${encodeURIComponent(row.id)}`}>去标注</Link>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="新建锚作文"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMut.isPending}
        width={640}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            aggregate_level: "L2",
            is_published: true,
            trait_levels: defaultTraitLevels("L2"),
          }}
          onFinish={(v) => {
            const levels =
              v.trait_levels && Object.keys(v.trait_levels).length
                ? v.trait_levels
                : defaultTraitLevels(v.aggregate_level);
            createMut.mutate({
              question_id: v.question_id,
              title: v.title ?? "",
              content: v.content,
              aggregate_level: v.aggregate_level,
              trait_levels: levels,
              is_published: v.is_published ?? true,
            });
          }}
        >
          <Form.Item name="question_id" label="题目" rules={[{ required: true }]}>
            <Select showSearch optionFilterProp="label" options={qOptions} />
          </Form.Item>
          <Form.Item
            name="title"
            label="锚作文名称"
            extra="仅用于后台列表与标注页识别，不是正文里的作文标题；正文标题请写在「正文」第一行。"
          >
            <Input placeholder="如：L4 一类文标尺 · 论证充分" />
          </Form.Item>
          <Form.Item name="aggregate_level" label="综合档位">
            <Select
              options={LEVELS.map((l) => ({ value: l, label: levelSelectLabel(l) }))}
              onChange={(lv) => form.setFieldsValue({ trait_levels: defaultTraitLevels(lv) })}
            />
          </Form.Item>
          <Form.Item name="content" label="正文" rules={[{ required: true, min: 20 }]}>
            <Input.TextArea rows={6} placeholder="完整锚作文正文（≥20 字）" />
          </Form.Item>
          <Form.Item name="is_published" label="立即发布" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Descriptions size="small" column={2} title="八大维度档位（可逐项修改）">
            {TRAIT_IDS.map((tid) => (
              <Descriptions.Item key={tid} label={TRAIT_LABELS[tid]}>
                <Form.Item name={["trait_levels", tid]} noStyle>
                  <Select
                    size="small"
                    style={{ width: 140 }}
                    options={LEVELS.map((l) => ({ value: l, label: levelSelectLabel(l) }))}
                  />
                </Form.Item>
              </Descriptions.Item>
            ))}
          </Descriptions>
          {!form.getFieldValue("trait_levels") && (
            <span style={{ fontSize: 12, color: "#888" }}>默认随综合档：{aggregateWatch}</span>
          )}
        </Form>
      </Modal>
    </Space>
  );
}
