import { Button, Card, Form, Input, InputNumber, List, Modal, Statistic, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";

export default function AdminGoldPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: samples } = useQuery({
    queryKey: ["admin-gold"],
    queryFn: () => api<{ id: string; title: string; question_id: string }[]>("/admin/gold-samples"),
  });

  const { data: regression } = useQuery({
    queryKey: ["admin-gold-regression"],
    queryFn: () =>
      api<{ pass_rate: number | null; avg_delta: number | null; run_count: number; recent: unknown[] }>(
        "/admin/gold-regression",
      ),
  });

  const create = useMutation({
    mutationFn: (v: Record<string, unknown>) =>
      api("/admin/gold-samples", { method: "POST", body: JSON.stringify(v) }),
    onSuccess: () => {
      message.success("已添加金标");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["admin-gold"] });
    },
  });

  const run = useMutation({
    mutationFn: (id: string) => api(`/admin/gold-samples/${id}/run`, { method: "POST", body: "{}" }),
    onSuccess: () => {
      message.success("跑分完成（需管理员 BYOK）");
      qc.invalidateQueries({ queryKey: ["admin-gold-regression"] });
    },
    onError: (e) => message.error(String(e)),
  });

  return (
    <Card title="金标回归">
      <Statistic title="回归通过率（Δ≤2）" value={regression?.pass_rate ?? "—"} suffix="%" />
      <Statistic title="平均偏差" value={regression?.avg_delta ?? "—"} style={{ marginTop: 16 }} />
      <Button style={{ margin: "16px 0" }} onClick={() => setOpen(true)}>
        录入金标
      </Button>
      <List
        dataSource={samples ?? []}
        renderItem={(item) => (
          <List.Item actions={[<Button key="r" loading={run.isPending} onClick={() => run.mutate(item.id)}>跑分</Button>]}>
            {item.title}
          </List.Item>
        )}
      />
      <Modal title="金标样本" open={open} onCancel={() => setOpen(false)} onOk={() => form.submit()} width={640}>
        <Form form={form} layout="vertical" onFinish={(v) => create.mutate(v)}>
          <Form.Item name="question_id" label="题目 ID" rules={[{ required: true }]}>
            <Input placeholder="demo-essay-001" />
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="reference_answer" label="金标作文" rules={[{ required: true }]}>
            <Input.TextArea rows={8} />
          </Form.Item>
          <Form.Item name="expected_score_min" label="期望分下限">
            <InputNumber />
          </Form.Item>
          <Form.Item name="expected_score_max" label="期望分上限">
            <InputNumber />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
