import { Alert, Card, Col, Row, Space, Typography } from "antd";
import { Link } from "react-router-dom";

const LINKS = [
  { to: "/admin/prompts", title: "Prompt 版本", desc: "管理大作文批改系统 Prompt，设为生效后用户批改立即使用新版本。" },
  { to: "/admin/gold", title: "金标回归", desc: "录入金标作文、跑分对比期望区间，监控 Prompt/模型漂移。" },
  { to: "/admin/questions", title: "金标参考题", desc: "维护评测用题干/材料（不对学员展示；用户端自备材料批改）。" },
  { to: "/admin/disputes", title: "评分争议", desc: "处理用户争议，AI 复核说明与 CSV 导出。" },
  { to: "/admin/jobs", title: "批改任务", desc: "排查失败 job、Key 错误与队列情况。" },
  { to: "/admin/codes", title: "激活码", desc: "爱发电发货批次与 grant。" },
  { to: "/admin/events", title: "埋点", desc: "关键行为事件审计。" },
];

export default function AdminHomePage() {
  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        message="V1 学员端：用户自备材料 + 题干 + 作文"
        description="学员不再从题库选题。教研侧「金标参考题」仅用于金标跑分与回归；线上批改 Prompt 与维度规则在此后台维护。"
      />
      <Row gutter={[16, 16]}>
        {LINKS.map((item) => (
          <Col xs={24} md={12} lg={8} key={item.to}>
            <Card title={<Link to={item.to}>{item.title}</Link>} size="small">
              <Typography.Text type="secondary">{item.desc}</Typography.Text>
            </Card>
          </Col>
        ))}
      </Row>
      <Card title="验货用户端" size="small">
        <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
          侧栏「体验用户端」与学员相同的自备题批改链路（需管理员 BYOK 才能提交批改）。
        </Typography.Paragraph>
        <Link to="/grading">打开批改页</Link>
      </Card>
    </Space>
  );
}
