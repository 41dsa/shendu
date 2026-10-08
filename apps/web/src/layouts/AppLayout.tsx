import { Button, Layout, Menu, Space, Typography } from "antd";
import {
  EditOutlined,
  FileTextOutlined,
  FundOutlined,
  HomeOutlined,
  ReadOutlined,
  UnorderedListOutlined,
  LogoutOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, logout } from "../api/client";

const { Sider, Content, Header } = Layout;

const items = [
  { key: "/", icon: <HomeOutlined />, label: "首页" },
  { key: "/grading", icon: <EditOutlined />, label: "批改" },
  { key: "/training", icon: <ReadOutlined />, label: "AI 训练" },
  { key: "/reports", icon: <FileTextOutlined />, label: "批改报告" },
  { key: "/abilities", icon: <FundOutlined />, label: "能力画像" },
  { key: "/issues", icon: <UnorderedListOutlined />, label: "问题本" },
  { key: "/me", icon: <UserOutlined />, label: "我的" },
  { key: "/purchase", icon: <ThunderboltOutlined />, label: "购买/激活" },
  { key: "/settings/ai", icon: <SettingOutlined />, label: "AI 设置" },
  { key: "/settings/exam", icon: <SettingOutlined />, label: "考试目标" },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const location = useLocation();
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ email: string }>("/auth/me"),
  });

  const selected = (() => {
    if (location.pathname.startsWith("/grading/jobs")) return "/grading";
    if (location.pathname.startsWith("/reports/")) return "/reports";
    const hit = items.find((i) => location.pathname === i.key || location.pathname.startsWith(i.key + "/"));
    return hit?.key ?? "/";
  })();

  const handleLogout = () => {
    logout();
    queryClient.clear();
    navigate("/login", { replace: true });
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        width={200}
        theme="light"
        breakpoint="lg"
        collapsedWidth={0}
        style={{ borderRight: "1px solid #f0f0f0" }}
      >
        <div style={{ padding: 16, fontWeight: 700, color: "#1677ff" }}>智观申论</div>
        <Menu mode="inline" selectedKeys={[selected]} items={items} onClick={(e) => navigate(e.key)} />
      </Sider>
      <Layout>
        <Header className="app-header">
          <span className="app-header-title">AI申论教练</span>
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
