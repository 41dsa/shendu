import { Alert, Button, Card, Form, Input, InputNumber, List, Modal, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";

type QRow = {
  id: string;
  title: string;
  prompt: string;
  material?: string;
  score: number;
  word_limit: number;
  material_structured?: { word_min?: number; word_max?: number };
  scoring_points: unknown[];
  published: boolean;
};

const DEFAULT_RUBRIC = `[
  {"id": "D01", "label": "立意与观点", "max_score": 10, "required": true, "ability": "A1"},
  {"id": "D02", "label": "结构与层次", "max_score": 10, "required": true, "ability": "A2"},
  {"id": "D03", "label": "论证与素材", "max_score": 10, "required": true, "ability": "A3"},
  {"id": "D04", "label": "语言表达", "max_score": 10, "required": true, "ability": "A4"}
]`;

export default function AdminQuestionsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form] = Form.useForm();

  const { data } = useQuery({
    queryKey: ["admin-questions"],
    queryFn: () => api<QRow[]>("/admin/questions"),
  });

  const save = useMutation({
    mutationFn: (values: Record<string, unknown>) => {
      const body = {
        ...values,
        scoring_points: JSON.parse(String(values.scoring_points_json || "[]")),
        word_min: values.word_min,
        word_max: values.word_max,
        published: false,
      };
      if (editId) {
        return api(`/admin/questions/${editId}`, { method: "PUT", body: JSON.stringify(body) });
      }
      return api("/admin/questions", { method: "POST", body: JSON.stringify(body) });
    },
    onSuccess: () => {
      message.success("已保存");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["admin-questions"] });
    },
    onError: (e) => message.error(String(e)),
  });

  const openEdit = (row?: QRow) => {
    setEditId(row?.id ?? null);
    form.setFieldsValue({
      title: row?.title ?? "",
      prompt: row?.prompt ?? "",
      material: row?.material ?? "",
      score: row?.score ?? 40,
      word_limit: row?.word_limit ?? 1200,
      word_min: row?.material_structured?.word_min ?? 800,
      word_max: row?.material_structured?.word_max ?? 1200,
      scoring_points_json: JSON.stringify(row?.scoring_points ?? JSON.parse(DEFAULT_RUBRIC), null, 2),
    });
    setOpen(true);
  };

  return (
    <Card
      title="金标参考题"
      extra={
        <Button type="primary" onClick={() => openEdit()}>
          新建参考题
        </Button>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="不对学员端展示"
        description="学员在批改页自备材料与题干。此处题目仅用于金标样本绑定、Prompt 回归与教研存档；新建题默认不发布到旧题库 API。"
      />
      <List
        dataSource={data ?? []}
        locale={{ emptyText: "暂无参考题，可先新建或保留 init_db 中的 demo-essay-001 用于金标。" }}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Button key="e" onClick={() => openEdit(item)}>
                编辑
              </Button>,
            ]}
          >
            <List.Item.Meta title={item.title} description={`ID: ${item.id}`} />
          </List.Item>
        )}
      />
      <Modal
        title={editId ? "编辑参考题" : "新建参考题"}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        width={720}
      >
        <Form form={form} layout="vertical" onFinish={(v) => save.mutate(v)}>
          <Form.Item name="title" label="标题（教研备注）" rules={[{ required: true }]}>
            <Input placeholder="如：2024 国考副省级 · 数字化治理" />
          </Form.Item>
          <Form.Item name="prompt" label="题干与作答要求" rules={[{ required: true }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="material" label="给定材料">
            <Input.TextArea rows={4} placeholder="与真实试卷一致，供金标跑分使用" />
          </Form.Item>
          <Form.Item name="score" label="满分">
            <InputNumber min={1} max={100} />
          </Form.Item>
          <Form.Item name="word_min" label="字数下限">
            <InputNumber />
          </Form.Item>
          <Form.Item name="word_max" label="字数上限">
            <InputNumber />
          </Form.Item>
          <Form.Item name="word_limit" label="word_limit 字段（兼容）">
            <InputNumber />
          </Form.Item>
          <Form.Item name="scoring_points_json" label="评分维度 JSON">
            <Input.TextArea rows={6} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
