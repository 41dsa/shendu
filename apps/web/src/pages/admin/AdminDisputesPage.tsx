import { Button, Card, List, Tag } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getToken } from "../../api/client";

type Dispute = {
  id: string;
  report_id: string;
  reason: string;
  status: string;
  created_at: string;
};

export default function AdminDisputesPage() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["admin-disputes"],
    queryFn: () => api<Dispute[]>("/admin/disputes"),
  });

  const review = useMutation({
    mutationFn: (id: string) => api(`/admin/disputes/${id}/ai-review`, { method: "POST", body: "{}" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-disputes"] }),
  });

  return (
    <Card
      title="评分争议"
      extra={
        <Button
          onClick={async () => {
            const token = getToken();
            const res = await fetch("/api/admin/disputes/export.csv", {
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "disputes.csv";
            a.click();
          }}
        >
          导出 CSV
        </Button>
      }
    >
      <List
        dataSource={data ?? []}
        renderItem={(item) => (
          <List.Item
            actions={[
              item.status === "pending" ? (
                <Button key="r" onClick={() => review.mutate(item.id)}>
                  AI 复核
                </Button>
              ) : null,
            ]}
          >
            <List.Item.Meta
              title={
                <>
                  <Tag>{item.status}</Tag> 报告 {item.report_id.slice(0, 8)}…
                </>
              }
              description={item.reason}
            />
          </List.Item>
        )}
      />
    </Card>
  );
}
