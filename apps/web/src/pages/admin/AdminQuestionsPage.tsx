import { Button, Card, Form, Input, InputNumber, List, Modal, Switch, message } from "antd";
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
      qc.invalidateQueries({ queryKey: ["questions"] });
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
      published: row?.published ?? true,
      scoring_points_json: JSON.stringify(row?.scoring_points ?? [], null, 2),
    });
    setOpen(true);
  };

  return (
    <Card
      title="大作文题库"
      extra={
        <Button type="primary" onClick={() => openEdit()}>
          新建
        </Button>
      }
    >
      <List
        dataSource={data ?? []}
        renderItem={(item) => (
          <List.Item actions={[<Button key="e" onClick={() => openEdit(item)}>编辑</Button>]}>
            {item.title} {item.published ? "" : "（未发布）"}
          </List.Item>
        )}
      />
      <Modal
        title={editId ? "编辑题目" : "新建题目"}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        width={720}
      >
        <Form form={form} layout="vertical" onFinish={(v) => save.mutate(v)}>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="prompt" label="题干" rules={[{ required: true }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="material" label="参考背景">
            <Input.TextArea rows={2} />
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
          <Form.Item name="word_limit" label="word_limit 字段">
            <InputNumber />
          </Form.Item>
          <Form.Item name="published" label="发布" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="scoring_points_json" label="评分维度 JSON">
            <Input.TextArea rows={6} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
