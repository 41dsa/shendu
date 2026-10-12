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
  const [reviewerForm] = Form.useForm();
  const [embeddingForm] = Form.useForm();

  const { data: creds } = useQuery({
    queryKey: ["ai-creds"],
    queryFn: () => api<Cred[]>("/ai/credentials"),
  });
  const primary = creds?.find((c) => c.role === "primary");
  const consensus = creds?.find((c) => c.role === "consensus");
  const reviewer = creds?.find((c) => c.role === "reviewer");
  const embedding = creds?.find((c) => c.role === "embedding");

  useEffect(() => {
    primaryForm.setFieldsValue({
      base_url: primary?.base_url || "https://api.deepseek.com/v1",
      model: primary?.model || "deepseek-chat",
      save_tokens_mode: false,
    });
  }, [primary, primaryForm]);

  useEffect(() => {
    if (consensus?.configured) {
      consensusForm.setFieldsValue({
        base_url: consensus.base_url,
        model: consensus.model,
      });
    }
  }, [consensus, consensusForm]);

  useEffect(() => {
    if (reviewer?.configured) {
      reviewerForm.setFieldsValue({
        base_url: reviewer.base_url,
        model: reviewer.model,
      });
    }
  }, [reviewer, reviewerForm]);

  useEffect(() => {
    if (embedding?.configured) {
      embeddingForm.setFieldsValue({
        base_url: embedding.base_url,
        model: embedding.model,
      });
    }
  }, [embedding, embeddingForm]);

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

  const saveReviewer = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      api(`/ai/credentials/reviewer`, {
        method: "PUT",
        body: JSON.stringify({ ...values, save_tokens_mode: false }),
      }),
    onSuccess: () => {
      message.success("第三评审模型已保存");
      qc.invalidateQueries({ queryKey: ["ai-creds"] });
    },
    onError: (e) => message.error(String(e)),
  });

  const testReviewer = useMutation({
    mutationFn: () => api("/ai/test-connection", { method: "POST", body: JSON.stringify({ role: "reviewer" }) }),
    onSuccess: (res: { warning?: string }) => {
      if (res?.warning) message.warning(res.warning);
      else message.success("第三评审 Chat 连接成功");
    },
    onError: (e) => message.error(String(e)),
  });

  const saveEmbedding = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      api(`/ai/credentials/embedding`, {
        method: "PUT",
        body: JSON.stringify({ ...values, save_tokens_mode: false }),
      }),
    onSuccess: () => {
      message.success("Embedding 模型已保存");
      qc.invalidateQueries({ queryKey: ["ai-creds"] });
    },
    onError: (e) => message.error(String(e)),
  });

  const testEmbedding = useMutation({
    mutationFn: () => api("/ai/test-embedding", { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (res: { ok?: boolean; dimensions?: number; message?: string }) => {
      if (res?.ok) message.success(`Embedding 连通（维度 ${res.dimensions ?? "?"}）`);
      else message.warning(res?.message || "Embedding 未配置");
    },
    onError: (e) => message.error(String(e)),
  });

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="主模型（完整批改）">
        <Typography.Paragraph type="secondary">
          用于大作文完整批改：维度得分、问题与建议。必填。请任选厂商，但接口须为{" "}
          <strong>OpenAI 兼容</strong>的 Chat Completions（Base 一般为 …/v1，支持 JSON 结构化输出）。
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
          <Form.Item
            name="base_url"
            label="API Base URL"
            rules={[{ required: true }]}
            extra="示例：DeepSeek、通义、OpenAI、Azure OpenAI、自建网关等，只要兼容 OpenAI /v1/chat/completions。"
          >
            <Input placeholder="https://api.example.com/v1" />
          </Form.Item>
          <Form.Item name="model" label="模型名称" rules={[{ required: true }]}>
            <Input placeholder="厂商文档中的 chat 模型名" />
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
            <Input placeholder="可与主模型相同或换厂商，需您自行填写" />
          </Form.Item>
          <Form.Item
            name="model"
            label="模型名称"
            rules={[{ required: true }]}
            extra="可与主模型相同，或换更便宜/更快的模型只做总分复核。"
          >
            <Input placeholder="deepseek-chat / qwen-plus …" />
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

      <Card title="第三评审（点池 L2 共识，可选）">
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="用途"
          description="标准生产点池的多模型投票第三路；建议使用与主模型不同厂商/架构的 chat 模型。未配置时不影响批改主流程。"
        />
        <Form
          form={reviewerForm}
          layout="vertical"
          onFinish={(v) => {
            const payload: Record<string, unknown> = {
              base_url: v.base_url,
              model: v.model,
            };
            if (v.api_key?.trim()) payload.api_key = v.api_key.trim();
            saveReviewer.mutate(payload);
          }}
        >
          <Form.Item name="base_url" label="API Base URL" rules={[{ required: true }]}>
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item
            name="model"
            label="模型名称"
            rules={[{ required: true }]}
            extra="须为 Chat/对话模型，勿填 text-embedding 类模型；接口格式同 OpenAI Chat Completions。"
          >
            <Input placeholder="chat 模型名（见厂商文档）" />
          </Form.Item>
          <Form.Item
            name="api_key"
            label="API Key"
            rules={[{ required: !reviewer?.configured, min: 8 }]}
          >
            <Input.Password placeholder={reviewer?.configured ? `已配置 ${reviewer.api_key_masked}` : ""} />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={saveReviewer.isPending}>
              保存第三评审
            </Button>
            <Button onClick={() => testReviewer.mutate()} disabled={!reviewer?.configured}>
              测试 Chat 连接
            </Button>
          </Space>
        </Form>
      </Card>

      <Card title="Embedding 模型（L2 语义匹配，可选）">
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="与主模型独立，厂商可不同"
          description={
            <>
              主模型、共识、Embedding 可分别选择任意服务商，系统<strong>不会</strong>自动绑定厂商。
              Embedding 须为支持 <strong>OpenAI 兼容</strong> <code>/v1/embeddings</code>（或等价根路径 +
              <code>/embeddings</code>）的向量模型；Base 可填该服务的 /v1 根地址，保存后点「测试 Embedding」验证。
              未配置时规则预评仅能用关键词匹配，语义匹配会偏弱。
            </>
          }
        />
        <Form
          form={embeddingForm}
          layout="vertical"
          onFinish={(v) => {
            const payload: Record<string, unknown> = {
              base_url: v.base_url,
              model: v.model,
            };
            if (v.api_key?.trim()) payload.api_key = v.api_key.trim();
            saveEmbedding.mutate(payload);
          }}
        >
          <Form.Item
            name="base_url"
            label="API Base URL"
            rules={[{ required: true }]}
            extra="OpenAI 兼容 Embedding 网关的 /v1 根路径（与 Chat 是否同厂无关）。"
          >
            <Input placeholder="https://api.example.com/v1" />
          </Form.Item>
          <Form.Item
            name="model"
            label="Embedding 模型名称"
            rules={[{ required: true }]}
            extra="须为 text-embedding / embedding 类模型名，勿填 chat 模型；以厂商 OpenAI 兼容文档为准。"
          >
            <Input placeholder="text-embedding-3-small 或厂商 embedding 模型名" />
          </Form.Item>
          <Form.Item
            name="api_key"
            label="API Key"
            rules={[{ required: !embedding?.configured, min: 8 }]}
          >
            <Input.Password placeholder={embedding?.configured ? `已配置 ${embedding.api_key_masked}` : ""} />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={saveEmbedding.isPending}>
              保存 Embedding
            </Button>
            <Button onClick={() => testEmbedding.mutate()} disabled={!embedding?.configured}>
              测试 Embedding
            </Button>
          </Space>
        </Form>
      </Card>
    </Space>
  );
}
