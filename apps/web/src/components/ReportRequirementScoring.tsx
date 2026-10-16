import { Table, Tag, Typography } from "antd";

type Row = {
  key?: string;
  label?: string;
  required?: string;
  actual?: string;
  status?: string;
};

type Props = {
  summary?: {
    rows?: Row[];
  } | null;
};

const STATUS: Record<string, { text: string; color: string }> = {
  ok: { text: "达标", color: "success" },
  warn: { text: "注意", color: "warning" },
  fail: { text: "未达标", color: "error" },
  info: { text: "参考", color: "default" },
};

export default function ReportRequirementScoring({ summary }: Props) {
  const rows = summary?.rows ?? [];
  if (rows.length === 0) {
    return null;
  }

  return (
    <div style={{ marginTop: 16 }}>
      <Typography.Text strong>作答要求中的分值与评分情况</Typography.Text>
      <Typography.Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 8, fontSize: 13 }}>
        依据你提交的「作答要求」解析题目分值、字数与材料约束，并对照本次批改结果。「维度得分合计」为立意、结构、论证、语言等分项之和，应与报告总分接近。
      </Typography.Paragraph>
      <Table
        size="small"
        pagination={false}
        rowKey={(r) => r.key ?? r.label ?? ""}
        dataSource={rows}
        columns={[
          { title: "项目", dataIndex: "label", width: 108 },
          { title: "作答要求", dataIndex: "required" },
          { title: "本次情况", dataIndex: "actual" },
          {
            title: "状态",
            width: 72,
            render: (_, r) => {
              const s = STATUS[r.status ?? "info"] ?? STATUS.info;
              return <Tag color={s.color}>{s.text}</Tag>;
            },
          },
        ]}
      />
    </div>
  );
}
