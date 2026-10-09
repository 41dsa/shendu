import { Alert, Button, Card, Form, Input, InputNumber, List, Modal, Select, Statistic, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";

type GoldRow = {
  id: string;
  title: string;
  question_id: string;
};

type QRow = { id: string; title: string };

export default function AdminGoldPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: samples } = useQuery({
    queryKey: ["admin-gold"],
    queryFn: () => api<GoldRow[]>("/admin/gold-samples"),
  });

  const { data: questions } = useQuery({
    queryKey: ["admin-questions"],
    queryFn: () => api<QRow[]>("/admin/questions"),
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
      form.resetFields();
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

  const qOptions = (questions ?? []).map((q) => ({ value: q.id, label: `${q.title}（${q.id}）` }));

  return (
    <Card title="金标回归">
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="与用户端自备题批改分离"
        description="跑分使用下方绑定的「金标参考题」题干/材料 + 金标作文，验证 Prompt 与模型是否稳定；需在 AI 设置中配置管理员 BYOK。"
      />
      <Statistic title="回归通过率（Δ≤2）" value={regression?.pass_rate ?? "—"} suffix="%" />
      <Statistic title="平均偏差" value={regression?.avg_delta ?? "—"} style={{ marginTop: 16 }} />
      <Button type="primary" style={{ margin: "16px 0" }} onClick={() => setOpen(true)}>
        录入金标
      </Button>
      <List
        dataSource={samples ?? []}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Button key="r" loading={run.isPending} onClick={() => run.mutate(item.id)}>
                跑分
              </Button>,
            ]}
          >
            <List.Item.Meta title={item.title} description={`参考题 ID：${item.question_id}`} />
          </List.Item>
        )}
      />
      <Modal title="金标样本" open={open} onCancel={() => setOpen(false)} onOk={() => form.submit()} width={640}>
        <Form form={form} layout="vertical" onFinish={(v) => create.mutate(v)}>
          <Form.Item name="question_id" label="绑定金标参考题" rules={[{ required: true }]}>
            <Select
              showSearch
              placeholder="选择或搜索参考题"
              options={qOptions}
              optionFilterProp="label"
              notFoundContent="请先在「金标参考题」新建题目"
            />
          </Form.Item>
          <Form.Item name="title" label="样本名称" rules={[{ required: true }]}>
            <Input placeholder="如：金标-数字化治理-中等稿" />
          </Form.Item>
          <Form.Item name="reference_answer" label="金标作文（标准答案稿）" rules={[{ required: true }]}>
            <Input.TextArea rows={8} />
          </Form.Item>
          <Form.Item name="expected_score_min" label="期望分下限">
            <InputNumber min={0} max={40} />
          </Form.Item>
          <Form.Item name="expected_score_max" label="期望分上限">
            <InputNumber min={0} max={40} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
