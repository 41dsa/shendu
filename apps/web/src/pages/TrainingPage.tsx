import { Button, Card, List, Space, Tabs, Tag, Typography, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

type Task = {
  task_key: string;
  kind: string;
  title: string;
  level: string;
  ability_id?: string;
  ability_name?: string;
  instructions?: string;
  question_id?: string | null;
  estimated_minutes?: number;
  focus_tag?: string;
};

type RecordRow = {
  id: string;
  kind: string;
  title: string;
  level: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  result_note?: string | null;
};

type Plan = {
  today_tasks: Task[];
  special_tasks: Task[];
  today_progress: { done: number; target: number };
  records: RecordRow[];
};

export default function TrainingPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["training-plan"],
    queryFn: () => api<Plan>("/coach/training/plan"),
  });

  const start = useMutation({
    mutationFn: (task: Task) =>
      api<RecordRow>("/coach/training/records", {
        method: "POST",
        body: JSON.stringify({
          kind: task.kind,
          title: task.title,
          level: task.level,
          ability_id: task.ability_id,
          focus_tag: task.focus_tag,
          instructions: task.instructions,
          question_id: task.question_id,
        }),
      }),
    onSuccess: () => {
      message.success("已开始训练，请前往批改完成练习");
      qc.invalidateQueries({ queryKey: ["training-plan"] });
      qc.invalidateQueries({ queryKey: ["coach-home"] });
    },
    onError: (e) => message.error(String(e)),
  });

  const complete = useMutation({
    mutationFn: (id: string) =>
      api(`/coach/training/records/${id}/complete`, {
        method: "POST",
        body: JSON.stringify({ result_note: "已在批改中完成练习" }),
      }),
    onSuccess: () => {
      message.success("已标记完成");
      qc.invalidateQueries({ queryKey: ["training-plan"] });
      qc.invalidateQueries({ queryKey: ["coach-home"] });
    },
  });

  const skip = useMutation({
    mutationFn: (id: string) =>
      api(`/coach/training/records/${id}/skip`, { method: "POST", body: "{}" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["training-plan"] }),
  });

  const renderTask = (task: Task) => (
    <List.Item
      actions={[
        <Button key="s" type="primary" loading={start.isPending} onClick={() => start.mutate(task)}>
          开始
        </Button>,
        task.question_id ? (
          <Button key="g">
            <Link to={`/grading?question=${task.question_id}`}>去批改</Link>
          </Button>
        ) : null,
      ]}
    >
      <List.Item.Meta
        title={
          <>
            {task.title} <Tag>{task.level}</Tag>
            {task.ability_name && <Tag color="blue">{task.ability_name}</Tag>}
          </>
        }
        description={
          <>
            {task.instructions}
            {task.estimated_minutes ? (
              <Typography.Text type="secondary"> · 约 {task.estimated_minutes} 分钟</Typography.Text>
            ) : null}
          </>
        }
      />
    </List.Item>
  );

  const pending = (data?.records ?? []).filter((r) => r.status === "pending");

  return (
    <Card title="AI 训练" loading={isLoading}>
      <Tabs
        items={[
          {
            key: "today",
            label: `今日训练 (${data?.today_progress.done ?? 0}/${data?.today_progress.target ?? 3})`,
            children: (
              <List dataSource={data?.today_tasks ?? []} renderItem={renderTask} locale={{ emptyText: "暂无推荐" }} />
            ),
          },
          {
            key: "special",
            label: "专项训练",
            children: (
              <List dataSource={data?.special_tasks ?? []} renderItem={renderTask} locale={{ emptyText: "暂无推荐" }} />
            ),
          },
          {
            key: "records",
            label: "训练记录",
            children: (
              <Space direction="vertical" style={{ width: "100%" }}>
                {pending.length > 0 && (
                  <>
                    <Typography.Text strong>进行中</Typography.Text>
                    <List
                      dataSource={pending}
                      renderItem={(r) => (
                        <List.Item
                          actions={[
                            <Button key="c" onClick={() => complete.mutate(r.id)}>
                              标记完成
                            </Button>,
                            <Button key="k" onClick={() => skip.mutate(r.id)}>
                              跳过
                            </Button>,
                          ]}
                        >
                          {r.title} <Tag>{r.level}</Tag>
                        </List.Item>
                      )}
                    />
                  </>
                )}
                <Typography.Text strong>历史</Typography.Text>
                <List
                  dataSource={(data?.records ?? []).filter((r) => r.status !== "pending")}
                  renderItem={(r) => (
                    <List.Item>
                      {r.title} · {r.status} · {new Date(r.created_at).toLocaleString()}
                    </List.Item>
                  )}
                />
              </Space>
            ),
          },
        ]}
      />
    </Card>
  );
}
