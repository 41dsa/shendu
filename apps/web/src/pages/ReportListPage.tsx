import { Button, Card, List, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

type ReportItem = {
  id: string;
  created_at: string;
  total_score: number | null;
  confidence: string | null;
  grading_job_id: string;
};

export default function ReportListPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["reports"],
    queryFn: () => api<ReportItem[]>("/reports"),
  });

  return (
    <Card title="批改报告">
      {isLoading ? (
        <Typography.Text type="secondary">加载中…</Typography.Text>
      ) : !data?.length ? (
        <Typography.Text type="secondary">暂无报告，请先在「批改」中提交一篇大作文。</Typography.Text>
      ) : (
        <List
          dataSource={data}
          renderItem={(item) => (
            <List.Item
              actions={[
                <Button type="primary" key="view">
                  <Link to={`/reports/${item.id}`}>查看详情</Link>
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={
                  <SpaceInline score={item.total_score} confidence={item.confidence} time={item.created_at} />
                }
                description={`任务 ID：${item.grading_job_id.slice(0, 8)}…`}
              />
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}

function SpaceInline({
  score,
  confidence,
  time,
}: {
  score: number | null;
  confidence: string | null;
  time: string;
}) {
  return (
    <span>
      {score != null ? `${score} 分` : "批改报告"}{" "}
      {confidence && <Tag color="blue">{confidence}</Tag>}{" "}
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {new Date(time).toLocaleString()}
      </Typography.Text>
    </span>
  );
}
