import { Card, List, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

type IssueRow = {
  tag: string;
  label: string;
  count: number;
  last_severity: string | null;
  last_report_id: string;
};

export default function IssueBookPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["issue-book"],
    queryFn: () => api<IssueRow[]>("/coach/issues"),
  });

  return (
    <Card title="问题本">
      {isLoading ? (
        <Typography.Text type="secondary">加载中…</Typography.Text>
      ) : !data?.length ? (
        <Typography.Text type="secondary">暂无聚合问题，完成批改后会自动收录。</Typography.Text>
      ) : (
        <List
          dataSource={data}
          renderItem={(item) => (
            <List.Item
              actions={[
                <Link key="r" to={`/reports/${item.last_report_id}`}>
                  最近报告
                </Link>,
              ]}
            >
              <List.Item.Meta
                title={
                  <>
                    <Tag color="orange">{item.label}</Tag>
                    <Typography.Text type="secondary">出现 {item.count} 次</Typography.Text>
                  </>
                }
                description={item.last_severity ? `最近严重程度：${item.last_severity}` : undefined}
              />
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
