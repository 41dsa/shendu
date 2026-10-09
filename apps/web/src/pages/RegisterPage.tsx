import { Button, Card, Form, Input, Typography, message } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { api, setToken } from "../api/client";

export default function RegisterPage() {
  const navigate = useNavigate();

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      const res = await api<{ access_token: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setToken(res.access_token);
      message.success("注册成功");
      const me = await api<{ role: string }>("/auth/me");
      navigate(me.role === "admin" ? "/admin" : "/purchase");
    } catch (e) {
      message.error(String(e));
    }
  };

  return (
    <div style={{ maxWidth: 420, margin: "80px auto" }}>
      <Card title="注册">
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: "email" }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 8 }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            注册
          </Button>
        </Form>
        <Typography.Paragraph style={{ marginTop: 16 }}>
          已有账号？<Link to="/login">登录</Link>
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
