import { Button, Card, List, Modal, Space, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { issueBadgeText } from "../utils/issueDisplay";
import { issueTypeTagStyle, severityLabel, severityVisual } from "../utils/severityLabel";

type IssueReportEntry = {
  report_id: string;
  created_at: string;
  total_score?: number | null;
  severity?: string | null;
};

type IssueRow = {
  tag: string;
  label: string;
  count: number;
  last_severity: string | null;
  last_report_id: string;
  reports?: IssueReportEntry[];
};

export default function IssueBookPage() {
  const [openIssue, setOpenIssue] = useState<IssueRow | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["issue-book"],
    queryFn: () => api<IssueRow[]>("/coach/issues"),
  });

  const reportList = openIssue?.reports?.length
    ? openIssue.reports
    : openIssue?.last_report_id
      ? [
          {
            report_id: openIssue.last_report_id,
            created_at: "",
            total_score: null,
            severity: openIssue.last_severity,
          },
        ]
      : [];

  return (
    <>
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
                  <Button key="reports" type="link" onClick={() => setOpenIssue(item)}>
                    查看报告 ({item.reports?.length ?? item.count})
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <>
                      <Tag style={issueTypeTagStyle}>{issueBadgeText({ tag: item.label })}</Tag>
                      <Typography.Text type="secondary">出现 {item.count} 次</Typography.Text>
                    </>
                  }
                  description={
                    item.last_severity ? (
                      <Space size={4}>
                        <Typography.Text type="secondary">最近严重程度</Typography.Text>
                        <Tag style={severityVisual(item.last_severity).style}>
                          {severityLabel(item.last_severity)}
                        </Tag>
                      </Space>
                    ) : undefined
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      <Modal
        title={
          openIssue ? (
            <Space wrap>
              <span>同类问题报告</span>
              <Tag style={issueTypeTagStyle}>{issueBadgeText({ tag: openIssue.label })}</Tag>
            </Space>
          ) : (
            "同类问题报告"
          )
        }
        open={!!openIssue}
        onCancel={() => setOpenIssue(null)}
        footer={null}
        width={520}
      >
        <List
          size="small"
          dataSource={reportList}
          locale={{ emptyText: "暂无关联报告" }}
          renderItem={(entry) => (
            <List.Item
              actions={[
                <Link key="open" to={`/reports/${entry.report_id}`}>
                  打开报告
                </Link>,
              ]}
            >
              <Space direction="vertical" size={2}>
                <Typography.Text>
                  {entry.created_at
                    ? new Date(entry.created_at).toLocaleString()
                    : "批改报告"}
                  {entry.total_score != null ? ` · ${entry.total_score} 分` : ""}
                </Typography.Text>
                {entry.severity ? (
                  <Tag style={severityVisual(entry.severity).style} bordered={false}>
                    {severityLabel(entry.severity)}
                  </Tag>
                ) : null}
              </Space>
            </List.Item>
          )}
        />
      </Modal>
    </>
  );
}
