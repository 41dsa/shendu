import { Button, Card, Form, Input, Switch, message, Space } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

type Cred = {
  role: string;
  base_url: string;
  model: string;
  api_key_masked: string;
  configured: boolean;
};

export default function SettingsAiPage() {
  const qc = useQueryClient();
  const { data: creds } = useQuery({
    queryKey: ["ai-creds"],
    queryFn: () => api<Cred[]>("/ai/credentials"),
  });
  const primary = creds?.find((c) => c.role === "primary");

  const save = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      api(`/ai/credentials/primary`, {
        method: "PUT",
        body: JSON.stringify(values),
      }),
    onSuccess: () => {
      message.success("已保存");
      qc.invalidateQueries({ queryKey: ["ai-creds"] });
      qc.invalidateQueries({ queryKey: ["entitlement"] });
    },
    onError: (e) => message.error(String(e)),
  });

  const test = useMutation({
    mutationFn: () => api("/ai/test-connection", { method: "POST", body: JSON.stringify({ role: "primary" }) }),
    onSuccess: (res: { warning?: string }) => {
      if (res?.warning) message.warning(res.warning);
      else message.success("连接成功（含 JSON 批改能力检测）");
    },
    onError: (e) => message.error(String(e)),
  });

  return (
    <Card title="AI 服务（BYOK）">
      <Form
        layout="vertical"
        initialValues={{
          base_url: primary?.base_url || "https://api.deepseek.com/v1",
          model: primary?.model || "deepseek-chat",
          save_tokens_mode: false,
        }}
        onFinish={(v) => {
          const payload: Record<string, unknown> = {
            base_url: v.base_url,
            model: v.model,
            save_tokens_mode: v.save_tokens_mode ?? false,
          };
          if (v.api_key?.trim()) payload.api_key = v.api_key.trim();
          save.mutate(payload);
        }}
      >
        <Form.Item name="base_url" label="API Base URL" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="model" label="模型名称" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="api_key" label="API Key" rules={[{ required: !primary?.configured, min: 8 }]}>
          <Input.Password placeholder={primary?.configured ? `已配置 ${primary.api_key_masked}` : ""} />
        </Form.Item>
        <Form.Item name="save_tokens_mode" label="省流模式（少共识）" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Space>
          <Button type="primary" htmlType="submit" loading={save.isPending}>
            保存
          </Button>
          <Button onClick={() => test.mutate()} disabled={!primary?.configured}>
            测试连接
          </Button>
        </Space>
      </Form>
    </Card>
  );
}
