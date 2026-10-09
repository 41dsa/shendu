import { Button, Card, Form, Input, Typography, message } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { api, setToken } from "../api/client";

export default function LoginPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      const res = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setToken(res.access_token);
      message.success("登录成功");
      const me = await api<{ role: string }>("/auth/me");
      navigate(me.role === "admin" ? "/admin" : "/");
    } catch (e) {
      message.error(String(e));
    }
  };

  return (
    <div style={{ maxWidth: 420, margin: "80px auto" }}>
      <Card title="登录">
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: "email" }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 8 }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            登录
          </Button>
        </Form>
        <Typography.Paragraph style={{ marginTop: 16 }}>
          没有账号？<Link to="/register">注册</Link>
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
