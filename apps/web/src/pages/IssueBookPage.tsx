import { Button, Card, List, Modal, Select, Space, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { ABILITY_DIMENSIONS, abilityName } from "../utils/abilityDimensions";
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
  issue_name?: string | null;
  ability_id?: string | null;
  count: number;
  last_severity: string | null;
  last_report_id: string;
  reports?: IssueReportEntry[];
};

export default function IssueBookPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const abilityFilter = searchParams.get("ability") || undefined;
  const reportLimit = searchParams.get("limit") || undefined;
  const [openIssue, setOpenIssue] = useState<IssueRow | null>(null);

  const queryKey = useMemo(
    () => ["issue-book", abilityFilter ?? "all", reportLimit ?? "default"],
    [abilityFilter, reportLimit],
  );

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => {
      const params = new URLSearchParams();
      if (abilityFilter) params.set("ability_id", abilityFilter);
      if (reportLimit) params.set("limit", reportLimit);
      const q = params.toString();
      return api<IssueRow[]>(`/coach/issues${q ? `?${q}` : ""}`);
    },
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

  const filterLabel = abilityName(abilityFilter);

  return (
    <>
      <Card
        title="问题本"
        extra={
          <Space wrap>
            <Typography.Text type="secondary">能力维</Typography.Text>
            <Select
              allowClear
              placeholder="全部"
              style={{ minWidth: 160 }}
              value={abilityFilter}
              options={ABILITY_DIMENSIONS.map((d) => ({ value: d.id, label: d.name }))}
              onChange={(value) => {
                if (value) {
                  setSearchParams({ ability: value });
                } else {
                  setSearchParams({});
                }
              }}
            />
            <Link to="/abilities">能力画像</Link>
          </Space>
        }
      >
        {filterLabel && (
          <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
            当前筛选：{filterLabel}
            {reportLimit ? ` · 最近 ${reportLimit} 篇批改（与能力画像一致）` : " · 最近 80 篇批改"}。
          </Typography.Paragraph>
        )}
        {isLoading ? (
          <Typography.Text type="secondary">加载中…</Typography.Text>
        ) : !data?.length ? (
          <Typography.Text type="secondary">
            {filterLabel ? `「${filterLabel}」下暂无聚合问题。` : "暂无聚合问题，完成批改后会自动收录。"}
          </Typography.Text>
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
                    <Space wrap size={4}>
                      <Tag style={issueTypeTagStyle}>
                        {item.issue_name ?? issueBadgeText({ tag: item.label })}
                      </Tag>
                      {item.ability_id && abilityName(item.ability_id) && (
                        <Tag color="geekblue">{abilityName(item.ability_id)}</Tag>
                      )}
                      <Typography.Text type="secondary">出现 {item.count} 次</Typography.Text>
                    </Space>
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
              <Tag style={issueTypeTagStyle}>
                {openIssue.issue_name ?? issueBadgeText({ tag: openIssue.label })}
              </Tag>
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
