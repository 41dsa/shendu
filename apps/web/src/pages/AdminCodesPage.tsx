import { Button, Card, Form, InputNumber, List, message } from "antd";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export default function AdminCodesPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<{ role: string }>("/auth/me") });
  const gen = useMutation({
    mutationFn: (count: number) =>
      api<{ codes: string[]; unused_total: number }>("/admin/redeem-codes/generate", {
        method: "POST",
        body: JSON.stringify({ count }),
      }),
    onSuccess: (res) => message.success(`已生成 ${res.codes.length} 个，池内剩余 ${res.unused_total}`),
    onError: (e) => message.error(String(e)),
  });

  if (me.data?.role !== "admin") {
    return <Card>需要管理员账号（注册时 BOOTSTRAP_ADMIN_EMAIL 匹配）</Card>;
  }

  return (
    <Card title="激活码生成">
      <Form onFinish={(v) => gen.mutate(v.count)} layout="inline">
        <Form.Item name="count" initialValue={10} label="数量">
          <InputNumber min={1} max={100} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={gen.isPending}>
          生成
        </Button>
      </Form>
      {gen.data?.codes && (
        <List
          style={{ marginTop: 16 }}
          header="本次生成"
          dataSource={gen.data.codes}
          renderItem={(c) => <List.Item>{c}</List.Item>}
        />
      )}
    </Card>
  );
}
