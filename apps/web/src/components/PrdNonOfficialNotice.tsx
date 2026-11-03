import { Typography } from "antd";

const DEFAULT = "AI 辅助诊断，非官方评分；请勿将区间或总分当作精确估分。";

type Props = {
  compact?: boolean;
  style?: React.CSSProperties;
};

export default function PrdNonOfficialNotice({ compact, style }: Props) {
  if (compact) {
    return (
      <Typography.Text type="secondary" style={{ fontSize: 12, ...style }}>
        {DEFAULT}
      </Typography.Text>
    );
  }
  return (
    <Typography.Paragraph type="secondary" style={{ marginBottom: 16, fontSize: 13, ...style }}>
      {DEFAULT}
    </Typography.Paragraph>
  );
}
