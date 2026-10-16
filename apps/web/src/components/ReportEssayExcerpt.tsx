import { Typography } from "antd";
import { EDIT_FRAGMENT_MARK_STYLE } from "./EssayHighlightView";
import { splitForHighlight, type HighlightRange } from "../utils/highlightEssay";

type Props = {
  excerpt: string;
  highlightRanges?: HighlightRange[];
};

/** 评语下方内联原文摘录（可选标红待改片段） */
export default function ReportEssayExcerpt({ excerpt, highlightRanges }: Props) {
  const body = excerpt.replace(/^「/, "").replace(/」$/, "");
  const ranges = highlightRanges ?? [];
  const pieces = splitForHighlight(body, ranges);

  return (
    <Typography.Paragraph
      style={{
        marginBottom: 0,
        marginTop: 4,
        padding: "8px 10px",
        borderRadius: 6,
        background: "#fafafa",
        border: "1px solid #f0f0f0",
        fontSize: 13,
        lineHeight: 1.75,
        color: "rgba(0,0,0,0.65)",
      }}
    >
      「
      {pieces.map((p, i) =>
        p.highlight ? (
          <mark key={i} style={EDIT_FRAGMENT_MARK_STYLE}>
            {p.text}
          </mark>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
      」
    </Typography.Paragraph>
  );
}
