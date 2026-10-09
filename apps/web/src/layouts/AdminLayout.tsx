import { Button, Layout, Menu, Space, Typography } from "antd";
import { ExperimentOutlined, LogoutOutlined } from "@ant-design/icons";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, logout } from "../api/client";

const { Sider, Content, Header } = Layout;

const adminItems = [
  { key: "/admin", label: <Link to="/admin">概览</Link> },
  { key: "/admin/prompts", label: <Link to="/admin/prompts">Prompt 版本</Link> },
  { key: "/admin/gold", label: <Link to="/admin/gold">金标回归</Link> },
  { key: "/admin/questions", label: <Link to="/admin/questions">金标参考题</Link> },
  { key: "/admin/disputes", label: <Link to="/admin/disputes">评分争议</Link> },
  { key: "/admin/jobs", label: <Link to="/admin/jobs">批改任务</Link> },
  { key: "/admin/codes", label: <Link to="/admin/codes">激活码</Link> },
  { key: "/admin/events", label: <Link to="/admin/events">埋点</Link> },
];

export default function AdminLayout() {
  const loc = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const selected =
    adminItems.find((i) => (i.key === "/admin" ? loc.pathname === "/admin" : loc.pathname.startsWith(i.key!)))
      ?.key ?? "/admin";

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ email: string; role: string }>("/auth/me"),
  });

  const handleLogout = () => {
    logout();
    queryClient.clear();
    navigate("/login", { replace: true });
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider width={200} theme="light" breakpoint="lg" collapsedWidth={0} style={{ borderRight: "1px solid #f0f0f0" }}>
        <div style={{ padding: 16, fontWeight: 700, color: "#1677ff" }}>教研后台</div>
        <Menu mode="inline" selectedKeys={[selected]} items={adminItems} />
        <div style={{ padding: "12px 16px", borderTop: "1px solid #f0f0f0", marginTop: 8 }}>
          <Button block icon={<ExperimentOutlined />} onClick={() => navigate("/grading")}>
            体验用户端
          </Button>
        </div>
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space>
            <span className="app-header-title">AI申论教练 · 管理</span>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              管理员
            </Typography.Text>
          </Space>
          <Space>
            {me?.email && (
              <Typography.Text type="secondary" className="app-header-email">
                {me.email}
              </Typography.Text>
            )}
            <Button type="text" icon={<LogoutOutlined />} onClick={handleLogout}>
              退出登录
            </Button>
          </Space>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
