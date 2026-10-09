import { Button, Card, Form, Input, List, Modal, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";

type PromptRow = { id: string; name: string; is_active: boolean; content_preview: string };

export default function AdminPromptsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const { data } = useQuery({
    queryKey: ["admin-prompts"],
    queryFn: () => api<PromptRow[]>("/admin/prompt-versions"),
  });

  const create = useMutation({
    mutationFn: (v: { name: string; content: string }) =>
      api("/admin/prompt-versions", { method: "POST", body: JSON.stringify(v) }),
    onSuccess: () => {
      message.success("已创建");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["admin-prompts"] });
    },
  });

  const activate = useMutation({
    mutationFn: (id: string) => api(`/admin/prompt-versions/${id}/activate`, { method: "POST", body: "{}" }),
    onSuccess: () => {
      message.success("已设为生效");
      qc.invalidateQueries({ queryKey: ["admin-prompts"] });
    },
  });

  return (
    <Card title="Prompt 版本" extra={<Button onClick={() => setOpen(true)}>新建版本</Button>}>
      <List
        dataSource={data ?? []}
        renderItem={(item) => (
          <List.Item
            actions={[
              !item.is_active ? (
                <Button key="a" onClick={() => activate.mutate(item.id)}>
                  设为生效
                </Button>
              ) : (
                <span key="a">当前生效</span>
              ),
            ]}
          >
            <List.Item.Meta title={item.name} description={item.content_preview} />
          </List.Item>
        )}
      />
      <Modal title="新建 Prompt" open={open} onCancel={() => setOpen(false)} onOk={() => form.submit()} width={640}>
        <Form
          form={form}
          layout="vertical"
          onFinish={(v) => create.mutate(v)}
          initialValues={{ purpose: "essay_grading" }}
        >
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="content" label="System Prompt" rules={[{ required: true }]}>
            <Input.TextArea rows={12} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
