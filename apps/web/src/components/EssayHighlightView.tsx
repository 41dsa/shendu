import { Typography } from "antd";
import { splitEssayMarkdownBlocks } from "../utils/essayMarkdownBlocks";
import { splitForHighlight, type HighlightRange } from "../utils/highlightEssay";

const MARK_STYLE = {
  padding: "0 1px",
  borderRadius: 2,
  boxDecorationBreak: "clone" as const,
  WebkitBoxDecorationBreak: "clone" as const,
};

type Props = {
  content: string;
  ranges: HighlightRange[];
  emptyLabel?: string;
  highlightBg: string;
  highlightTitle?: string;
  /** 高亮片段前展示 1、2、3… 序号（与下方说明列表对照） */
  showSegmentIndex?: boolean;
  panelBg?: string;
  borderColor?: string;
};

function rangesInBlock(blockStart: number, blockEnd: number, ranges: HighlightRange[]): HighlightRange[] {
  const local: HighlightRange[] = [];
  for (const r of ranges) {
    if (r.end <= blockStart || r.start >= blockEnd) continue;
    local.push({
      start: Math.max(blockStart, r.start) - blockStart,
      end: Math.min(blockEnd, r.end) - blockStart,
      reason: r.reason,
      segmentIndex: r.segmentIndex,
    });
  }
  return local;
}

export function SegmentIndexLabel({ index }: { index: number }) {
  return (
    <span
      aria-hidden
      style={{
        fontSize: 12,
        fontWeight: 600,
        color: "#cf1322",
        marginRight: 2,
        userSelect: "none",
      }}
    >
      {index}.
    </span>
  );
}

function BlockText({
  text,
  ranges,
  highlightBg,
  highlightTitle,
  showSegmentIndex,
}: {
  text: string;
  ranges: HighlightRange[];
  highlightBg: string;
  highlightTitle?: string;
  showSegmentIndex?: boolean;
}) {
  const pieces = splitForHighlight(text, ranges);
  return (
    <>
      {pieces.map((p, i) =>
        p.highlight ? (
          <span key={i} style={{ display: "inline" }}>
            {showSegmentIndex && p.segmentIndex != null ? (
              <SegmentIndexLabel index={p.segmentIndex} />
            ) : null}
            <mark
              title={
                p.segmentIndex != null
                  ? `改动 ${p.segmentIndex}${p.reason ? `：${p.reason}` : ""}`
                  : p.reason || highlightTitle
              }
              style={{ ...MARK_STYLE, background: highlightBg, color: "inherit" }}
            >
              {p.text}
            </mark>
          </span>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </>
  );
}

export default function EssayHighlightView({
  content,
  ranges,
  emptyLabel,
  highlightBg,
  highlightTitle,
  showSegmentIndex,
  panelBg = "#fafafa",
  borderColor = "#f0f0f0",
}: Props) {
  const blocks = splitEssayMarkdownBlocks(content);

  return (
    <div
      style={{
        marginTop: 8,
        padding: "12px 12px 24px",
        border: `1px solid ${borderColor}`,
        borderRadius: 8,
        background: panelBg,
        maxHeight: 480,
        overflowX: "hidden",
        overflowY: "auto",
        wordBreak: "break-word",
        lineHeight: 1.85,
        fontSize: 14,
        color: "rgba(0,0,0,0.88)",
      }}
    >
      {!content ? (
        <Typography.Text type="secondary">{emptyLabel ?? "暂无正文"}</Typography.Text>
      ) : blocks.length === 0 ? (
        <p style={{ margin: 0, whiteSpace: "pre-wrap", textIndent: "2em" }}>
          <BlockText
            text={content}
            ranges={ranges}
            highlightBg={highlightBg}
            highlightTitle={highlightTitle}
            showSegmentIndex={showSegmentIndex}
          />
        </p>
      ) : (
        blocks.map((block, idx) => {
          const useCssIndent = !block.isTitle && !block.hasCharIndent;
          return (
            <p
              key={`${block.start}-${idx}`}
              style={{
                margin: idx === blocks.length - 1 ? "0 0 0" : "0 0 14px",
                whiteSpace: "pre-wrap",
                textIndent: useCssIndent ? "2em" : 0,
                fontWeight: block.isTitle ? 600 : 400,
              }}
            >
              <BlockText
                text={block.text}
                ranges={rangesInBlock(block.start, block.end, ranges)}
                highlightBg={highlightBg}
                highlightTitle={highlightTitle}
                showSegmentIndex={showSegmentIndex}
              />
            </p>
          );
        })
      )}
    </div>
  );
}
