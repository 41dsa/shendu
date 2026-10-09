import {
  EditOutlined,
  FileTextOutlined,
  FundOutlined,
  HomeOutlined,
  ReadOutlined,
  RollbackOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  UnorderedListOutlined,
  UserOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";

type MenuItem = Required<MenuProps>["items"][number];

const learnerItems: MenuItem[] = [
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

/** 管理员在「体验用户端」下保留的验货入口（批改链路 + BYOK + 用量） */
const adminPreviewItems: MenuItem[] = [
  { key: "/grading", icon: <EditOutlined />, label: "批改" },
  { key: "/reports", icon: <FileTextOutlined />, label: "批改报告" },
  { key: "/settings/ai", icon: <SettingOutlined />, label: "AI 设置" },
  { key: "/me", icon: <UserOutlined />, label: "我的" },
];

export function buildAppSidebarMenu(isAdmin: boolean): MenuItem[] {
  if (!isAdmin) {
    return learnerItems;
  }
  return [
    { key: "/admin", icon: <RollbackOutlined />, label: "教研后台" },
    { type: "divider" },
    { type: "group", label: "体验用户端", children: adminPreviewItems },
  ];
}

/** 管理员侧栏未开放、直接输入 URL 时也重定向（验货请用「体验用户端」四项） */
export const ADMIN_BLOCKED_LEARNER_PATHS = [
  "/purchase",
  "/activate",
  "/settings/exam",
  "/training",
  "/abilities",
  "/issues",
];
