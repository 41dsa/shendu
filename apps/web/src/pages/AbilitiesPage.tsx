import { Card, Progress, Space, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

type RelatedIssue = { code: string; label: string; count: number };

type AbilitiesResponse = {
  overall: number | null;
  report_count: number;
  data_confidence: string;
  dimensions: {
    id: string;
    name: string;
    score: number | null;
    sample_count: number;
    related_issues?: RelatedIssue[];
  }[];
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
              {d.id === "A5" && d.sample_count > 0 ? "（含字数达标推算）" : ""}
            </Typography.Text>
            {(d.related_issues?.length ?? 0) > 0 && (
              <div style={{ marginTop: 8 }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  同类问题（问题本）：
                </Typography.Text>
                <Space wrap size={[4, 4]} style={{ marginTop: 4 }}>
                  {d.related_issues!.map((issue) => (
                    <Link key={issue.code} to={`/issues?ability=${d.id}&limit=20`}>
                      <Tag>
                        {issue.label} ×{issue.count}
                      </Tag>
                    </Link>
                  ))}
                  <Link to={`/issues?ability=${d.id}&limit=20`}>
                    <Tag color="blue">查看全部</Tag>
                  </Link>
                </Space>
              </div>
            )}
            {(d.related_issues?.length ?? 0) === 0 && (
              <Typography.Text type="secondary" style={{ display: "block", fontSize: 12, marginTop: 4 }}>
                暂无收录的同类问题标签。
              </Typography.Text>
            )}
          </div>
        ))}
      </Space>
    </Card>
  );
}
