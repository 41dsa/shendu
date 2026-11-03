import { Button, Layout, Menu, Space, Tag, Typography } from "antd";
import { LogoutOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { buildAppSidebarMenu } from "../config/sidebarMenu";
import { api, logout } from "../api/client";

const { Sider, Content, Header } = Layout;

export default function AppLayout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const location = useLocation();
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ email: string; role: string }>("/auth/me"),
  });

  const isAdmin = me?.role === "admin";
  const menuItems = buildAppSidebarMenu(isAdmin);

  const selected = (() => {
    if (location.pathname.startsWith("/grading/jobs")) return "/grading";
    if (location.pathname.startsWith("/reports/")) return "/reports";
    if (location.pathname.startsWith("/admin")) return "/admin";
    const flatKeys = menuItems.flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      if ("children" in item && item.children) {
        return item.children.map((c) => (c && "key" in c ? String(c.key) : ""));
      }
      return "key" in item ? [String(item.key)] : [];
    });
    const hit = flatKeys.find((k) => k && (location.pathname === k || location.pathname.startsWith(`${k}/`)));
    return hit ?? (isAdmin ? "/grading" : "/");
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
        {isAdmin && (
          <div style={{ padding: "0 16px 8px" }}>
            <Tag color="blue">体验用户端</Tag>
          </div>
        )}
        <Menu mode="inline" selectedKeys={[selected]} items={menuItems} onClick={(e) => navigate(e.key)} />
      </Sider>
      <Layout>
        <Header className="app-header">
          <span className="app-header-title">{isAdmin ? "AI申论教练 · 验货" : "AI申论教练"}</span>
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
          <div style={{ padding: "8px 24px 0", maxWidth: 1200, margin: "0 auto" }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              AI 辅助诊断，非官方评分；报告区间与能力等级未经命题方校准，请勿对外宣称准确估分。
            </Typography.Text>
          </div>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
