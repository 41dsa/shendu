import { Card, Progress, Space, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

type AbilitiesResponse = {
  overall: number | null;
  report_count: number;
  data_confidence: string;
  dimensions: { id: string; name: string; score: number | null; sample_count: number }[];
};

const CONF_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低", none: "无数据" };

export default function AbilitiesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["abilities"],
    queryFn: () => api<AbilitiesResponse>("/coach/abilities"),
  });

  return (
    <Card title="能力画像（大作文五维）" loading={isLoading}>
      <Space direction="vertical" style={{ width: "100%" }} size="large">
        <div>
          <Typography.Title level={3} style={{ margin: 0 }}>
            {data?.overall ?? "—"}
            {data?.overall != null ? " 分" : ""}
          </Typography.Title>
          <Typography.Text type="secondary">
            基于最近 {data?.report_count ?? 0} 篇批改 · 数据可信度{" "}
            <Tag>{CONF_LABEL[data?.data_confidence ?? "none"]}</Tag>
          </Typography.Text>
        </div>
        {(data?.dimensions ?? []).map((d) => (
          <div key={d.id}>
            <Typography.Text>{d.name}</Typography.Text>
            <Progress
              percent={d.score ?? 0}
              format={() => (d.score != null ? `${d.score}` : "—")}
              status={d.score != null && d.score < 60 ? "exception" : "normal"}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              样本维度条目 {d.sample_count} 条
            </Typography.Text>
          </div>
        ))}
      </Space>
    </Card>
  );
}
