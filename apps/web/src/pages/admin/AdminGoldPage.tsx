import { Alert, Button, Card, Form, Input, InputNumber, List, Modal, Select, Statistic, Table, message } from "antd";
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

  const { data: calibration } = useQuery({
    queryKey: ["admin-calibration-metrics"],
    queryFn: () =>
      api<{
        overall_gate_passed: boolean;
        gold_regression: { qwk: number | null; gate_passed: boolean; gate_reason: string; pair_count: number };
      }>("/admin/calibration/metrics"),
  });

  const { data: regression } = useQuery({
    queryKey: ["admin-gold-regression"],
    queryFn: () =>
      api<{
        pass_rate: number | null;
        avg_delta: number | null;
        run_count: number;
        standard_versions: number[];
        by_standard_version: {
          standard_version: number | null;
          run_count: number;
          pass_rate: number | null;
          avg_delta: number | null;
        }[];
        recent: {
          id: string;
          gold_sample_id: string;
          ai_score: number | null;
          score_delta: number | null;
          standard_version: number | null;
          created_at: string;
        }[];
      }>("/admin/gold-regression"),
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
        description="跑分使用绑定参考题 + 金标作文。纯 AI 金标：services/api 下 seed_ai_gold.py（高/中/低）→ run_ai_gold_regression.py；跑分需管理员 BYOK。"
      />
      {calibration?.gold_regression ? (
        <Alert
          type={calibration.overall_gate_passed ? "success" : "warning"}
          showIcon
          style={{ marginBottom: 16 }}
          message={`V3 校准门禁 · QWK ${calibration.gold_regression.qwk?.toFixed(3) ?? "—"}（${calibration.gold_regression.pair_count} 对金标）`}
          description={calibration.gold_regression.gate_reason}
        />
      ) : null}
      <Statistic title="回归通过率（Δ≤2）" value={regression?.pass_rate ?? "—"} suffix="%" />
      <Statistic title="平均偏差" value={regression?.avg_delta ?? "—"} style={{ marginTop: 16 }} />
      {(regression?.by_standard_version?.length ?? 0) > 0 && (
        <Table
          size="small"
          style={{ marginTop: 16 }}
          pagination={false}
          rowKey={(r) => String(r.standard_version ?? "none")}
          title={() => "按考试标准版本分组（近 100 次跑分）"}
          dataSource={regression!.by_standard_version!}
          columns={[
            {
              title: "标准版本",
              dataIndex: "standard_version",
              render: (v: number | null) => (v != null ? `v${v}` : "无发布标准"),
            },
            { title: "次数", dataIndex: "run_count", width: 72 },
            {
              title: "通过率（Δ≤2）",
              dataIndex: "pass_rate",
              render: (v: number | null) => (v != null ? `${v}%` : "—"),
            },
            { title: "平均偏差", dataIndex: "avg_delta", render: (v: number | null) => v ?? "—" },
          ]}
        />
      )}
      {(regression?.recent?.length ?? 0) > 0 && (
        <List
          size="small"
          header="最近跑分"
          style={{ marginTop: 16 }}
          dataSource={regression!.recent!.slice(0, 5)}
          renderItem={(r) => (
            <List.Item>
              AI {r.ai_score ?? "—"} / Δ {r.score_delta ?? "—"}
              {r.standard_version != null ? ` / 标准 v${r.standard_version}` : " / 无发布标准"}
            </List.Item>
          )}
        />
      )}
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
