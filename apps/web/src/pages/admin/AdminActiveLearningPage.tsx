import { Alert, Button, Card, Space, Table, Tag, Tooltip, Typography, message } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiDownload, formatApiErrorMessage } from "../../api/client";
import {
  activeLearningReasonColor,
  activeLearningReasonHint,
  activeLearningReasonLabel,
  formatActiveLearningQuestionId,
  formatActiveLearningSnapshot,
  formatActiveLearningTime,
} from "../../utils/activeLearningDisplay";

type PoolRow = {
  id: string;
  reason: string;
  priority: number;
  status: string;
  submission_id: string | null;
  question_id: string | null;
  snapshot: Record<string, unknown> | null;
  created_at: string | null;
};

export default function AdminActiveLearningPage() {
  const [exporting, setExporting] = useState(false);
  const { data, refetch, isFetching } = useQuery({
    queryKey: ["admin-active-learning", "open"],
    queryFn: () => api<PoolRow[]>("/admin/active-learning/pool?status=open&limit=200"),
  });

  const handleExport = async () => {
    setExporting(true);
    try {
      await apiDownload(
        "/admin/active-learning/export.jsonl?status=open",
        "active_learning_pool.jsonl",
      );
      message.success("复核数据已开始下载");
    } catch (e) {
      message.error(formatApiErrorMessage(e, "导出失败，请确认已登录管理员账号"));
    } finally {
      setExporting(false);
    }
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        主动学习难例池
      </Typography.Title>
      <Alert
        type="info"
        showIcon
        message="批改已成功，但机器对本次结果不够自信，自动列入待教研复核队列。"
        description="常见情况：多模型对维度等级意见不一致、证据偏少、标准匹配偏低、档位在边界上、或用户申诉。可导出数据供教研标注；更新 Rubric 后重新发布并跑合规门禁。"
      />
      <Card
        size="small"
        extra={
          <Space>
            <Button onClick={() => refetch()} loading={isFetching}>
              刷新
            </Button>
            <Button type="primary" loading={exporting} onClick={() => void handleExport()}>
              导出复核数据
            </Button>
          </Space>
        }
      >
        <Table
          rowKey="id"
          size="small"
          pagination={{ pageSize: 15 }}
          dataSource={data ?? []}
          columns={[
            {
              title: "入池原因",
              dataIndex: "reason",
              width: 130,
              render: (r: string) => {
                const label = activeLearningReasonLabel(r);
                const hint = activeLearningReasonHint(r);
                return hint ? (
                  <Tooltip title={hint}>
                    <Tag color={activeLearningReasonColor(r)}>{label}</Tag>
                  </Tooltip>
                ) : (
                  <Tag color={activeLearningReasonColor(r)}>{label}</Tag>
                );
              },
            },
            {
              title: "优先级",
              dataIndex: "priority",
              width: 72,
              render: (p: number) => (Number.isFinite(p) ? p.toFixed(2) : "—"),
            },
            {
              title: "题目",
              dataIndex: "question_id",
              width: 110,
              ellipsis: true,
              render: (q: string | null) => formatActiveLearningQuestionId(q),
            },
            {
              title: "提交编号",
              dataIndex: "submission_id",
              width: 108,
              ellipsis: true,
              render: (id: string | null) =>
                id ? (
                  <Tooltip title={id}>
                    <Typography.Text copyable={{ text: id }}>{id.slice(0, 8)}…</Typography.Text>
                  </Tooltip>
                ) : (
                  "—"
                ),
            },
            {
              title: "入池时诊断摘要",
              dataIndex: "snapshot",
              render: (s: Record<string, unknown> | null) => {
                const lines = formatActiveLearningSnapshot(s);
                return (
                  <Typography.Paragraph
                    style={{ marginBottom: 0, fontSize: 12, lineHeight: 1.55 }}
                    ellipsis={{ rows: 4, expandable: true, symbol: "展开" }}
                  >
                    {lines.map((line, i) => (
                      <span key={`${i}-${line.slice(0, 12)}`}>
                        {line}
                        {i < lines.length - 1 ? <br /> : null}
                      </span>
                    ))}
                  </Typography.Paragraph>
                );
              },
            },
            {
              title: "入池时间",
              dataIndex: "created_at",
              width: 168,
              render: (t: string | null) => formatActiveLearningTime(t),
            },
          ]}
        />
      </Card>
    </Space>
  );
}
