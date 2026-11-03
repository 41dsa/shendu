import { Alert, Button, Card, Form, Input, List, Modal, Select, Space, Tag, Typography, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../../api/client";
import { showApiError } from "../../api/errors";

type PromptRow = {
  id: string;
  name: string;
  purpose: string;
  is_active: boolean;
  content_preview: string;
};

const PURPOSE_ZH: Record<string, { label: string; group: "grading" | "standard" }> = {
  essay_grading: {
    label: "Trait 路径 · 报告润色（引擎已定档，LLM 不改分）",
    group: "grading",
  },
  essay_grading_custom: {
    label: "自备四档 · 主评定档（traditional_marking 专用）",
    group: "grading",
  },
  essay_consensus: { label: "Trait 路径 · 双路复核分", group: "grading" },
  standard_p01: { label: "标准生产 P01 · 题目标准", group: "standard" },
  standard_p02: { label: "标准生产 P02 · 材料分析", group: "standard" },
  standard_p03: { label: "标准生产 P03 · Rubric 候选", group: "standard" },
  standard_p04: { label: "标准生产 P04 · Rubric 合并", group: "standard" },
  standard_p05: { label: "标准生产 P05 · 标准验证", group: "standard" },
  standard_p06: { label: "标准生产 P06 · 答案匹配", group: "standard" },
  standard_p07: { label: "标准生产 P07 · 失分规则", group: "standard" },
};

const PURPOSE_CREATE_OPTIONS = [
  { value: "essay_grading", label: PURPOSE_ZH.essay_grading.label },
  { value: "essay_grading_custom", label: PURPOSE_ZH.essay_grading_custom.label },
  ...Object.entries(PURPOSE_ZH)
    .filter(([k]) => k.startsWith("standard_"))
    .map(([value, { label }]) => ({ value, label })),
];

export default function AdminPromptsPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [createPurpose, setCreatePurpose] = useState<string>("essay_grading");
  const [editId, setEditId] = useState<string | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ["admin-prompts"],
    queryFn: () => api<PromptRow[]>("/admin/prompt-versions"),
  });

  const grouped = useMemo(() => {
    const rows = data ?? [];
    const gradingTraitReport = rows.filter((r) => r.purpose === "essay_grading");
    const gradingCustomTraditional = rows.filter((r) => r.purpose === "essay_grading_custom");
    const gradingConsensus = rows.filter((r) => r.purpose === "essay_consensus");
    const standard = rows.filter((r) => PURPOSE_ZH[r.purpose]?.group === "standard");
    const knownPurposes = new Set(Object.keys(PURPOSE_ZH));
    const otherRows = rows.filter((r) => !knownPurposes.has(r.purpose));
    return {
      gradingTraitReport,
      gradingCustomTraditional,
      gradingConsensus,
      standard,
      other: otherRows,
    };
  }, [data]);

  const create = useMutation({
    mutationFn: (v: { name: string; content: string; purpose: string }) =>
      api("/admin/prompt-versions", { method: "POST", body: JSON.stringify(v) }),
    onSuccess: () => {
      message.success("已创建");
      setCreateOpen(false);
      createForm.resetFields();
      qc.invalidateQueries({ queryKey: ["admin-prompts"] });
    },
    onError: showApiError,
  });

  const activate = useMutation({
    mutationFn: (id: string) => api(`/admin/prompt-versions/${id}/activate`, { method: "POST", body: "{}" }),
    onSuccess: () => {
      message.success("已设为生效");
      qc.invalidateQueries({ queryKey: ["admin-prompts"] });
    },
    onError: showApiError,
  });

  const loadForEdit = async (id: string) => {
    const row = await api<{ name: string; content: string; is_active: boolean; purpose: string }>(
      `/admin/prompt-versions/${id}`,
    );
    editForm.setFieldsValue({ name: row.name, content: row.content });
    setEditId(id);
  };

  const update = useMutation({
    mutationFn: (v: { id: string; name: string; content: string }) =>
      api(`/admin/prompt-versions/${v.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name: v.name, content: v.content }),
      }),
    onSuccess: () => {
      message.success("已保存修改");
      setEditId(null);
      qc.invalidateQueries({ queryKey: ["admin-prompts"] });
    },
    onError: showApiError,
  });

  const openCreate = (purpose: string) => {
    setCreatePurpose(purpose);
    createForm.setFieldsValue({ purpose });
    setCreateOpen(true);
  };

  const renderList = (items: PromptRow[], emptyText: string) => (
    <List
      loading={isLoading}
      locale={{ emptyText }}
      dataSource={items}
      renderItem={(item) => {
        const meta = PURPOSE_ZH[item.purpose];
        const legacyMainGrader =
          item.purpose === "essay_grading" &&
          (/内置大作文批改|阅卷专家/i.test(item.name) || item.name.includes("旧版 LLM 主评"));
        return (
          <List.Item
            actions={[
              <Button key="edit" type="link" onClick={() => void loadForEdit(item.id)}>
                修改
              </Button>,
              !item.is_active ? (
                <Button key="a" type="link" onClick={() => activate.mutate(item.id)}>
                  设为生效
                </Button>
              ) : (
                <Tag key="a" color="green">
                  当前生效
                </Tag>
              ),
            ]}
          >
            <List.Item.Meta
              title={
                <Space wrap>
                  <span>{item.name}</span>
                  {meta ? <Tag color="blue">{meta.label}</Tag> : <Tag>{item.purpose}</Tag>}
                  {legacyMainGrader ? <Tag color="default">历史主评稿 · 勿设为生效</Tag> : null}
                </Space>
              }
              description={item.content_preview}
            />
          </List.Item>
        );
      }}
    />
  );

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        Prompt 版本管理
      </Typography.Title>
      <Alert
        type="info"
        showIcon
        message="PRD V1 下哪些还要留？"
        description={
          <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
            <li>
              <strong>Trait 路径 · 报告润色</strong>：题库与 Trait 自备共用；Trait 引擎已定档，此处 Prompt 只润色报告（勿写成「主评/阅卷定档」）。
            </li>
            <li>
              <strong>自备四档 · 主评</strong>：<code>CUSTOM_ESSAY_GRADING_MODE=traditional_marking</code> 时自备批改读下卡；与上卡无关，勿混用标签。
            </li>
            <li>
              <strong>可选 · 标准生产 P01～P07</strong>：仅在使用 LLM 生成<strong>标准卡/Rubric</strong>（考试标准引擎、自备题标准流水线）时读取；<strong>学员 Trait 批改主路径不经过这些 Prompt</strong>。若标准全走 stub/共识 JSON、不调 LLM，可少改或不改 P 系列。
            </li>
            <li>建议流程：修改文案 → 保存 → 对对应用途「设为生效」；同一用途同时只有一条生效。</li>
          </ul>
        }
      />

      <Card
        title="Trait 路径 · 报告润色 Prompt"
        extra={
          <Space wrap>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              essay_grading · 题库 / Trait 自备
            </Typography.Text>
            <Button type="primary" size="small" onClick={() => openCreate("essay_grading")}>
              新建报告润色
            </Button>
          </Space>
        }
      >
        {renderList(
          grouped.gradingTraitReport,
          "暂无版本。新建时用途选「Trait 路径 · 报告润色」；勿与四档主评混在同一命名下。",
        )}
      </Card>

      <Card
        title="自备四档 · 主评 Prompt"
        extra={
          <Space wrap>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              essay_grading_custom · 仅 traditional_marking
            </Typography.Text>
            <Button size="small" onClick={() => openCreate("essay_grading_custom")}>
              新建四档主评
            </Button>
          </Space>
        }
      >
        {renderList(grouped.gradingCustomTraditional, "暂无版本。运行 init_db 可种子默认四档 Prompt。")}
      </Card>

      {grouped.gradingConsensus.length > 0 ? (
        <Card title="Trait 路径 · 双路复核 Prompt">
          {renderList(grouped.gradingConsensus, "")}
        </Card>
      ) : null}

      <Card title="标准生产 Prompt（P01～P07）">
        {renderList(
          grouped.standard,
          "暂无标准生产 Prompt（init_db 会种子 P01～P07；纯 stub 标准生成可不维护）。",
        )}
        {grouped.other.length > 0 ? (
          <>
            <Typography.Text type="secondary">其他用途</Typography.Text>
            {renderList(grouped.other, "")}
          </>
        ) : null}
      </Card>

      <Modal
        title="新建 Prompt"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => createForm.submit()}
        width={720}
        destroyOnClose
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={(v) => create.mutate(v)}
          initialValues={{ purpose: createPurpose }}
        >
          <Form.Item name="purpose" label="用途" rules={[{ required: true }]}>
            <Select options={PURPOSE_CREATE_OPTIONS} />
          </Form.Item>
          <Form.Item name="name" label="版本名称（便于区分，勿用「大作文批改」笼统命名）" rules={[{ required: true }]}>
            <Input placeholder="如：Trait 报告润色 2026-03 / 自备四档主评 2026-03" />
          </Form.Item>
          <Form.Item name="content" label="System Prompt 正文" rules={[{ required: true }]}>
            <Input.TextArea rows={14} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="修改 Prompt"
        open={!!editId}
        onCancel={() => setEditId(null)}
        onOk={() => editForm.submit()}
        width={720}
        destroyOnClose
        confirmLoading={update.isPending}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={(v) => {
            if (!editId) return;
            update.mutate({ id: editId, name: v.name, content: v.content });
          }}
        >
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="content" label="System Prompt 正文" rules={[{ required: true }]}>
            <Input.TextArea rows={16} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
