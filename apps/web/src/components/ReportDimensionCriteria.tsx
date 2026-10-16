import { Space, Tag, Typography } from "antd";
import {
  criteriaHitTitle,
  criteriaScoreLine,
  statusLabel,
  statusTagColor,
  type PointHitRow,
} from "../utils/dimensionCriteria";

type Props = {
  hits: PointHitRow[];
  missedCount?: number;
  /** 该维度展示分为 0 时，调整采分点说明文案 */
  dimensionEarned?: number;
};

/** 维度卡片内：引擎采分点命中解析 */
export default function ReportDimensionCriteria({
  hits,
  missedCount = 0,
  dimensionEarned,
}: Props) {
  if (!hits.length && missedCount <= 0) return null;
  const dimZero = dimensionEarned != null && dimensionEarned <= 0;

  return (
    <div style={{ marginTop: 8 }}>
      <Typography.Text strong style={{ fontSize: 12, color: "rgba(0,0,0,0.55)" }}>
        采分点解析
      </Typography.Text>
      <Typography.Paragraph
        type="secondary"
        style={{ marginBottom: 6, marginTop: 4, fontSize: 11, lineHeight: 1.5 }}
      >
        {dimZero
          ? "以下为引擎在正文中的自动检出结果；该维度展示 0 分表示未命中预设采分点，不等于整卷「立意/结构等」完全缺失，请结合维度说明与顶部总分理解。"
          : "细项为引擎在正文中的自动检出；单条细项 0 分通常不会单独把上方维度分扣光，维度得分以上方「X/Y 分」为准。"}
      </Typography.Paragraph>
      <ul style={{ margin: "6px 0 0", paddingLeft: 18, listStyle: "disc" }}>
        {hits.map((hit, index) => {
          const scoreLine = criteriaScoreLine(hit);
          const note = String(hit.reason ?? hit.suggestion ?? "").trim();
          return (
            <li key={`${hit.point_id ?? index}-${index}`} style={{ marginBottom: 6 }}>
              <Space size={6} wrap align="start">
                <Tag color={statusTagColor(hit.status)} style={{ margin: 0 }}>
                  {statusLabel(hit.status)}
                </Tag>
                <Typography.Text style={{ fontSize: 13 }}>{criteriaHitTitle(hit)}</Typography.Text>
                {scoreLine ? (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {scoreLine}
                  </Typography.Text>
                ) : null}
              </Space>
              {note ? (
                <Typography.Paragraph
                  type="secondary"
                  style={{ marginBottom: 0, marginTop: 2, fontSize: 12, lineHeight: 1.6 }}
                >
                  {note.length > 120 ? `${note.slice(0, 117)}…` : note}
                </Typography.Paragraph>
              ) : null}
            </li>
          );
        })}
      </ul>
      {missedCount > 0 ? (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          另有 {missedCount} 个细采分点未在作答中检出足够表述（未单独计分）。
        </Typography.Text>
      ) : null}
    </div>
  );
}
