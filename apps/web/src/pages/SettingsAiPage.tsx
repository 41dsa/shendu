import { Alert, Button, Card, Form, Input, Space, Switch, Typography, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
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
  const [primaryForm] = Form.useForm();
  const [consensusForm] = Form.useForm();

  const { data: creds } = useQuery({
    queryKey: ["ai-creds"],
    queryFn: () => api<Cred[]>("/ai/credentials"),
  });
  const primary = creds?.find((c) => c.role === "primary");
  const consensus = creds?.find((c) => c.role === "consensus");

  useEffect(() => {
    primaryForm.setFieldsValue({
      base_url: primary?.base_url || "https://api.deepseek.com/v1",
      model: primary?.model || "deepseek-chat",
      save_tokens_mode: false,
    });
  }, [primary, primaryForm]);

  useEffect(() => {
    consensusForm.setFieldsValue({
      base_url: consensus?.base_url || primary?.base_url || "https://api.deepseek.com/v1",
      model: consensus?.model || primary?.model || "deepseek-chat",
    });
  }, [consensus, primary, consensusForm]);

  const savePrimary = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      api(`/ai/credentials/primary`, {
        method: "PUT",
        body: JSON.stringify(values),
      }),
    onSuccess: () => {
      message.success("主模型已保存");
      qc.invalidateQueries({ queryKey: ["ai-creds"] });
      qc.invalidateQueries({ queryKey: ["entitlement"] });
    },
    onError: (e) => message.error(String(e)),
  });

  const saveConsensus = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      api(`/ai/credentials/consensus`, {
        method: "PUT",
        body: JSON.stringify({ ...values, save_tokens_mode: false }),
      }),
    onSuccess: () => {
      message.success("共识模型已保存");
      qc.invalidateQueries({ queryKey: ["ai-creds"] });
    },
    onError: (e) => message.error(String(e)),
  });

  const testPrimary = useMutation({
    mutationFn: () => api("/ai/test-connection", { method: "POST", body: JSON.stringify({ role: "primary" }) }),
    onSuccess: (res: { warning?: string }) => {
      if (res?.warning) message.warning(res.warning);
      else message.success("主模型连接成功");
    },
    onError: (e) => message.error(String(e)),
  });

  const testConsensus = useMutation({
    mutationFn: () => api("/ai/test-connection", { method: "POST", body: JSON.stringify({ role: "consensus" }) }),
    onSuccess: (res: { warning?: string }) => {
      if (res?.warning) message.warning(res.warning);
      else message.success("共识模型连接成功");
    },
    onError: (e) => message.error(String(e)),
  });

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="主模型（完整批改）">
        <Typography.Paragraph type="secondary">
          用于大作文完整批改：维度得分、问题与建议。必填。
        </Typography.Paragraph>
        <Form
          form={primaryForm}
          layout="vertical"
          onFinish={(v) => {
            const payload: Record<string, unknown> = {
              base_url: v.base_url,
              model: v.model,
              save_tokens_mode: v.save_tokens_mode ?? false,
            };
            if (v.api_key?.trim()) payload.api_key = v.api_key.trim();
            savePrimary.mutate(payload);
          }}
        >
          <Form.Item name="base_url" label="API Base URL" rules={[{ required: true }]}>
            <Input placeholder="https://api.deepseek.com/v1" />
          </Form.Item>
          <Form.Item name="model" label="模型名称" rules={[{ required: true }]}>
            <Input placeholder="deepseek-chat" />
          </Form.Item>
          <Form.Item name="api_key" label="API Key" rules={[{ required: !primary?.configured, min: 8 }]}>
            <Input.Password placeholder={primary?.configured ? `已配置 ${primary.api_key_masked}` : ""} />
          </Form.Item>
          <Form.Item
            name="save_tokens_mode"
            label="省流模式"
            valuePropName="checked"
            extra="默认关闭。开启后将跳过第二次总分检验（双路复核），少一次模型调用；建议保持关闭以获得多次检验。"
          >
            <Switch />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={savePrimary.isPending}>
              保存主模型
            </Button>
            <Button onClick={() => testPrimary.mutate()} disabled={!primary?.configured}>
              测试连接
            </Button>
          </Space>
        </Form>
      </Card>

      <Card title="共识模型（双路复核，可选）">
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="何时会用到"
          description={
            <>
              主评完成后，在<strong>未开省流且字数达标</strong>时会固定进行第二次<strong>仅打总分</strong>的检验（双路复核）。
              未单独配置共识模型时，使用主模型；两路接近则提高总分数置信度，差距过大则采用主评并加宽合理区间。
            </>
          }
        />
        <Form
          form={consensusForm}
          layout="vertical"
          onFinish={(v) => {
            const payload: Record<string, unknown> = {
              base_url: v.base_url,
              model: v.model,
            };
            if (v.api_key?.trim()) payload.api_key = v.api_key.trim();
            saveConsensus.mutate(payload);
          }}
        >
          <Form.Item name="base_url" label="API Base URL" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="model"
            label="模型名称"
            rules={[{ required: true }]}
            extra="可与主模型相同，或换更便宜/更快的模型只做总分复核。"
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="api_key"
            label="API Key"
            rules={[{ required: !consensus?.configured, min: 8 }]}
            extra={!consensus?.configured ? "首次保存共识配置必填 Key（可与主模型相同）。" : undefined}
          >
            <Input.Password
              placeholder={
                consensus?.configured
                  ? `已配置 ${consensus.api_key_masked}`
                  : primary?.configured
                    ? "首次配置共识：填写 Key（可与主模型相同）"
                    : ""
              }
            />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={saveConsensus.isPending}>
              保存共识模型
            </Button>
            <Button
              onClick={() => testConsensus.mutate()}
              disabled={!consensus?.configured}
            >
              测试连接
            </Button>
          </Space>
          {consensus?.configured ? (
            <Typography.Text type="secondary" style={{ display: "block", marginTop: 12 }}>
              当前已启用独立共识配置；报告「评分依据」中会展示两路分数（若本次批改触发了复核）。
            </Typography.Text>
          ) : (
            <Typography.Text type="secondary" style={{ display: "block", marginTop: 12 }}>
              尚未单独配置：双路复核将使用主模型的 Base URL / 模型 / Key。
            </Typography.Text>
          )}
        </Form>
      </Card>
    </Space>
  );
}
