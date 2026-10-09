import { Card, List } from "antd";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

export default function AdminEventsPage() {
  const { data } = useQuery({
    queryKey: ["admin-events"],
    queryFn: () => api<{ event_name: string; user_id: string | null; created_at: string }[]>("/admin/events"),
  });

  return (
    <Card title="埋点事件">
      <List
        dataSource={data ?? []}
        renderItem={(item) => (
          <List.Item>
            {item.event_name} · user={item.user_id?.slice(0, 8) ?? "-"} · {new Date(item.created_at).toLocaleString()}
          </List.Item>
        )}
      />
    </Card>
  );
}
