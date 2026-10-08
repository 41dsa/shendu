import { Alert, Button, Card, Form, Input, message } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useEntitlement } from "../hooks/useEntitlement";

export default function ActivatePage() {
  const qc = useQueryClient();
  const { data: ent } = useEntitlement();
  const redeem = useMutation({
    mutationFn: (code: string) =>
      api<{ ok: boolean; message: string }>("/redeem", { method: "POST", body: JSON.stringify({ code }) }),
    onSuccess: (res) => {
      message.success(res.message);
      qc.invalidateQueries({ queryKey: ["entitlement"] });
    },
    onError: (e) => message.error(String(e)),
  });

  if (ent?.licensed) {
    return <Alert type="success" message="账号已激活" showIcon />;
  }

  return (
    <Card title="激活码兑换">
      <Form layout="vertical" onFinish={(v) => redeem.mutate(v.code.trim())}>
        <Form.Item name="code" label="激活码" rules={[{ required: true }]}>
          <Input placeholder="爱发电私信中的激活码" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={redeem.isPending}>
          兑换
        </Button>
      </Form>
      <Alert
        style={{ marginTop: 16 }}
        type="info"
        message="开发环境测试码：TEST-DEV-LICENSE（需先 init_db）"
      />
    </Card>
  );
}
