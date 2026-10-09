import { Button, Card, List, Progress, Space, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

type QueueJob = {
  id: string;
  status: string;
  current_step: string | null;
  created_at: string;
  error_message: string | null;
  report_id: string | null;
  label: string;
};

type QueueResponse = {
  max_concurrent: number;
  active_count: number;
  jobs: QueueJob[];
};

const STATUS_ZH: Record<string, { color: string; text: string }> = {
  queued: { color: "default", text: "排队中" },
  running: { color: "processing", text: "批改中" },
  succeeded: { color: "success", text: "已完成" },
  failed: { color: "error", text: "失败" },
};

type Props = {
  selectedJobId?: string | null;
  onSelectJob?: (jobId: string) => void;
  enabled?: boolean;
};

export default function GradingQueuePanel({ selectedJobId, onSelectJob, enabled = true }: Props) {
  const { data, isFetching } = useQuery({
    queryKey: ["grading-queue"],
    queryFn: () => api<QueueResponse>("/grading-jobs"),
    enabled,
    refetchInterval: (q) => {
      const active = q.state.data?.active_count ?? 0;
      return active > 0 ? 2500 : 15000;
    },
  });

  if (!enabled || !data) {
    return null;
  }

  const { max_concurrent, active_count, jobs } = data;
  const activeJobs = jobs.filter((j) => j.status === "queued" || j.status === "running");

  return (
    <Card
      size="small"
      title="批改队列"
      style={{ marginBottom: 16 }}
      extra={
        <Typography.Text type="secondary">
          进行中 {active_count}/{max_concurrent}
          {isFetching ? " · 刷新中" : ""}
        </Typography.Text>
      }
    >
      <Progress
        percent={Math.min(100, Math.round((active_count / max_concurrent) * 100))}
        status={active_count >= max_concurrent ? "exception" : active_count > 0 ? "active" : "normal"}
        format={() => `${active_count}/${max_concurrent}`}
        size="small"
        style={{ marginBottom: 12 }}
      />
      {active_count >= max_concurrent && (
        <Typography.Paragraph type="warning" style={{ marginBottom: 12, fontSize: 13 }}>
          队列已满，请等待下方任务完成后再提交；超过 5 分钟未动的排队任务会自动释放。
        </Typography.Paragraph>
      )}
      {activeJobs.length > 0 && (
        <>
          <Typography.Text strong style={{ fontSize: 13 }}>
            进行中
          </Typography.Text>
          <List
            size="small"
            style={{ marginTop: 8, marginBottom: 12 }}
            dataSource={activeJobs}
            renderItem={(job) => {
              const st = STATUS_ZH[job.status] ?? { color: "default", text: job.status };
              const selected = job.id === selectedJobId;
              return (
                <List.Item
                  actions={[
                    onSelectJob ? (
                      <Button
                        key="view"
                        type={selected ? "primary" : "link"}
                        size="small"
                        onClick={() => onSelectJob(job.id)}
                      >
                        {selected ? "当前" : "看进度"}
                      </Button>
                    ) : null,
                  ].filter(Boolean)}
                >
                  <List.Item.Meta
                    title={
                      <Space size={4} wrap>
                        <Tag color={st.color}>{st.text}</Tag>
                        <Typography.Text ellipsis style={{ maxWidth: 280 }}>
                          {job.label || job.id.slice(0, 8)}
                        </Typography.Text>
                      </Space>
                    }
                    description={
                      job.current_step
                        ? `步骤：${job.current_step}`
                        : new Date(job.created_at).toLocaleString()
                    }
                  />
                </List.Item>
              );
            }}
          />
        </>
      )}
      {jobs.length > 0 ? (
        <>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            最近任务
          </Typography.Text>
          <List
            size="small"
            style={{ marginTop: 8 }}
            dataSource={jobs.filter((j) => j.status !== "queued" && j.status !== "running").slice(0, 5)}
            locale={{ emptyText: "暂无已完成记录" }}
            renderItem={(job) => {
              const st = STATUS_ZH[job.status] ?? { color: "default", text: job.status };
              return (
                <List.Item
                  actions={[
                    job.status === "succeeded" && job.report_id ? (
                      <Link key="r" to={`/reports/${job.report_id}`}>
                        报告
                      </Link>
                    ) : job.status === "failed" && onSelectJob ? (
                      <Button type="link" size="small" onClick={() => onSelectJob(job.id)}>
                        详情
                      </Button>
                    ) : null,
                  ].filter(Boolean)}
                >
                  <Space size={4} wrap>
                    <Tag color={st.color}>{st.text}</Tag>
                    <Typography.Text ellipsis style={{ maxWidth: 300 }}>
                      {job.label}
                    </Typography.Text>
                  </Space>
                </List.Item>
              );
            }}
          />
        </>
      ) : (
        <Typography.Text type="secondary">提交批改后，任务会出现在这里。</Typography.Text>
      )}
    </Card>
  );
}
