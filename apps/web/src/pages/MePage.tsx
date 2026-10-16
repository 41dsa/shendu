import { Alert, Card, Descriptions, List, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

type MeSummary = {
  email: string;
  stats: {
    report_count: number;
    ai_calls: number;
    tokens_in: number;
    tokens_out: number;
  };
  dispute: { enabled: boolean; message: string };
};

export default function MePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["me-summary"],
    queryFn: () => api<MeSummary>("/coach/me"),
  });

  return (
    <Card title="我的" loading={isLoading}>
      <Descriptions column={1} bordered size="small">
        <Descriptions.Item label="账号">{data?.email}</Descriptions.Item>
        <Descriptions.Item label="大作文批改">{data?.stats.report_count ?? 0} 篇</Descriptions.Item>
        <Descriptions.Item label="AI 调用次数">{data?.stats.ai_calls ?? 0}</Descriptions.Item>
        <Descriptions.Item label="Token（入/出）">
          {data?.stats.tokens_in ?? 0} / {data?.stats.tokens_out ?? 0}
        </Descriptions.Item>
      </Descriptions>

      <Typography.Title level={5} style={{ marginTop: 24 }}>
        快捷入口
      </Typography.Title>
      <List
        size="small"
        dataSource={[
          { label: "考试目标", to: "/settings/exam" },
          { label: "AI 设置", to: "/settings/ai" },
          { label: "批改报告", to: "/reports" },
        ]}
        renderItem={(item) => (
          <List.Item>
            <Link to={item.to}>{item.label}</Link>
          </List.Item>
        )}
      />

      <Alert
        type="info"
        showIcon
        style={{ marginTop: 24 }}
        message="评分争议"
        description="可在任意批改报告页点击「评分争议」提交；教研在后台处理。"
      />
    </Card>
  );
}
