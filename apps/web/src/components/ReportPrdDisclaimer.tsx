import { Alert, Typography } from "antd";

const DEFAULT_DISCLAIMER =
  "本报告由 AI 诊断引擎生成，非官方阅卷分数；区间与能力等级未经命题方校准，请勿作为估分依据或对外宣称准确。";

type Props = {
  disclaimer?: string | null;
  nonOfficialNotice?: string | null;
  compact?: boolean;
};

export default function ReportPrdDisclaimer({ disclaimer, nonOfficialNotice, compact }: Props) {
  const body = (disclaimer && disclaimer.trim()) || DEFAULT_DISCLAIMER;
  const notice = (nonOfficialNotice && nonOfficialNotice.trim()) || "AI 辅助诊断，非官方评分结果。";
  if (compact) {
    return (
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0, fontSize: 12 }}>
        {notice} {body}
      </Typography.Paragraph>
    );
  }
  return (
    <Alert
      type="info"
      showIcon
      message={notice}
      description={body}
      style={{ marginBottom: 16 }}
    />
  );
}
