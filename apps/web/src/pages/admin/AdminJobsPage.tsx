import { Card, List, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

export default function AdminJobsPage() {
  const { data } = useQuery({
    queryKey: ["admin-jobs"],
    queryFn: () => api<{ id: string; status: string; error_message: string | null; created_at: string }[]>(
      "/admin/grading-jobs",
    ),
  });

  return (
    <Card title="批改任务（最近 50）">
      <List
        dataSource={data ?? []}
        renderItem={(item) => (
          <List.Item>
            <Tag>{item.status}</Tag> {item.id.slice(0, 8)}… {item.error_message ?? ""}{" "}
            <span style={{ color: "#999" }}>{new Date(item.created_at).toLocaleString()}</span>
          </List.Item>
        )}
      />
    </Card>
  );
}
