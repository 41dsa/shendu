import type { CSSProperties, RefObject, UIEvent } from "react";
import { useEffect, useRef } from "react";
import { Typography } from "antd";
import {
  hasLeadingIndent,
  highlightRangesForBody,
  splitEssayLayoutLines,
} from "../utils/essayMarkdownBlocks";
import { splitForHighlight, type HighlightRange } from "../utils/highlightEssay";

const MARK_STYLE = {
  padding: "0 1px",
  borderRadius: 2,
  boxDecorationBreak: "clone" as const,
  WebkitBoxDecorationBreak: "clone" as const,
};

/** 与右侧「局部改写范例」改动高亮一致，供修改片段说明复用 */
export const EDIT_FRAGMENT_MARK_STYLE: CSSProperties = {
  ...MARK_STYLE,
  background: "#ffa39e",
  color: "#a8071a",
  padding: "2px 4px",
  borderRadius: 3,
  border: "1px solid #ff7875",
  fontWeight: 500,
};

const HEADING_STYLE: Record<number, CSSProperties> = {
  1: { fontSize: 20, fontWeight: 700, textAlign: "center", lineHeight: 1.5 },
  2: { fontSize: 17, fontWeight: 650, textAlign: "center", lineHeight: 1.55 },
  3: { fontSize: 16, fontWeight: 600, lineHeight: 1.6 },
  4: { fontSize: 15, fontWeight: 600, lineHeight: 1.65 },
  5: { fontSize: 15, fontWeight: 600, lineHeight: 1.65 },
  6: { fontSize: 14, fontWeight: 600, lineHeight: 1.65 },
};

const PARAGRAPH_INDENT = "2em";

type Props = {
  content: string;
  ranges: HighlightRange[];
  emptyLabel?: string;
  highlightBg: string;
  highlightTitle?: string;
  showSegmentIndex?: boolean;
  panelBg?: string;
  borderColor?: string;
  scrollToChar?: number | null;
  activeHighlightBg?: string;
  /** 与问题摘录一致的红色待改标记 */
  issueMarkHighlight?: boolean;
  panelRef?: RefObject<HTMLDivElement | null>;
  onPanelScroll?: (event: UIEvent<HTMLDivElement>) => void;
  panelMinHeight?: number;
  /** 与上传作答一致：不推断居中标题、不追加段首缩进 */
  preserveOriginalLayout?: boolean;
  /** 参考范文模板：标题加深、段间留白、识别首行标题 */
  referenceTemplate?: boolean;
};

const REFERENCE_TITLE_STYLE: CSSProperties = {
  fontSize: 20,
  fontWeight: 800,
  textAlign: "center",
  lineHeight: 1.5,
  color: "#141414",
  margin: "0 0 14px",
};

function rangesOnLine(lineStart: number, lineEnd: number, ranges: HighlightRange[]): HighlightRange[] {
  const local: HighlightRange[] = [];
  for (const r of ranges) {
    if (r.end <= lineStart || r.start >= lineEnd) continue;
    local.push({
      start: Math.max(lineStart, r.start) - lineStart,
      end: Math.min(lineEnd, r.end) - lineStart,
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
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 18,
        height: 18,
        marginRight: 5,
        verticalAlign: "0.2em",
        borderRadius: "50%",
        background: "#fff",
        border: "2px solid #f5222d",
        fontSize: 11,
        fontWeight: 700,
        lineHeight: 1,
        color: "#f5222d",
        userSelect: "none",
        flexShrink: 0,
        boxShadow: "0 0 0 1px rgba(255,255,255,0.6)",
      }}
    >
      {index}
    </span>
  );
}

function BlockText({
  text,
  ranges,
  highlightBg,
  highlightTitle,
  showSegmentIndex,
  lineStartGlobal = 0,
  focusChar = null,
  activeHighlightBg,
  issueMarkHighlight,
}: {
  text: string;
  ranges: HighlightRange[];
  highlightBg: string;
  highlightTitle?: string;
  showSegmentIndex?: boolean;
  lineStartGlobal?: number;
  focusChar?: number | null;
  activeHighlightBg?: string;
  issueMarkHighlight?: boolean;
}) {
  const pieces = splitForHighlight(text, ranges);
  let localCursor = 0;
  return (
    <>
      {pieces.map((p, i) => {
        const gStart = lineStartGlobal + localCursor;
        localCursor += p.text.length;
        if (p.highlight) {
          const isFocus =
            focusChar != null && focusChar >= gStart && focusChar < gStart + p.text.length;
          const bg = isFocus && activeHighlightBg ? activeHighlightBg : highlightBg;
          return (
            <span
              key={i}
              style={{
                display: showSegmentIndex ? "inline-flex" : "inline",
                alignItems: "baseline",
                flexWrap: "wrap",
                maxWidth: "100%",
                verticalAlign: "baseline",
              }}
            >
              {showSegmentIndex && p.segmentIndex != null ? (
                <SegmentIndexLabel index={p.segmentIndex} />
              ) : null}
              <mark
                data-essay-char-start={gStart}
                title={
                  p.segmentIndex != null
                    ? `改动 ${p.segmentIndex}${p.reason ? `：${p.reason}` : ""}`
                    : p.reason || highlightTitle
                }
                style={
                  p.variant === "thesis_lead"
                    ? {
                        ...MARK_STYLE,
                        background: "#91caff",
                        color: "#141414",
                        fontWeight: 650,
                        padding: "1px 2px",
                        outline: isFocus ? "2px solid #1677ff" : undefined,
                      }
                    : showSegmentIndex
                      ? { ...EDIT_FRAGMENT_MARK_STYLE, background: bg }
                      : issueMarkHighlight
                        ? {
                            ...EDIT_FRAGMENT_MARK_STYLE,
                            outline: isFocus ? "2px solid #fa8c16" : undefined,
                          }
                        : {
                            ...MARK_STYLE,
                            background: bg,
                            color: "inherit",
                            outline: isFocus ? "2px solid #fa8c16" : undefined,
                          }
                }
              >
                {p.text}
              </mark>
            </span>
          );
        }
        return <span key={i}>{p.text}</span>;
      })}
    </>
  );
}

function BodyLine({
  line,
  lineStartGlobal,
  isParagraphStart,
  ranges,
  highlightBg,
  highlightTitle,
  showSegmentIndex,
  focusChar,
  activeHighlightBg,
  issueMarkHighlight,
  preserveOriginalLayout,
}: {
  line: string;
  lineStartGlobal: number;
  isParagraphStart: boolean;
  ranges: HighlightRange[];
  highlightBg: string;
  highlightTitle?: string;
  showSegmentIndex?: boolean;
  focusChar?: number | null;
  activeHighlightBg?: string;
  issueMarkHighlight?: boolean;
  preserveOriginalLayout?: boolean;
}) {
  const useSpacer = !preserveOriginalLayout && isParagraphStart && !hasLeadingIndent(line);
  if (preserveOriginalLayout) {
    return (
      <div
        data-essay-line-start={lineStartGlobal}
        style={{
          lineHeight: 1.85,
          minHeight: "1.85em",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        <BlockText
          text={line}
          ranges={ranges}
          highlightBg={highlightBg}
          highlightTitle={highlightTitle}
          showSegmentIndex={showSegmentIndex}
          lineStartGlobal={lineStartGlobal}
          focusChar={focusChar}
          activeHighlightBg={activeHighlightBg}
          issueMarkHighlight={issueMarkHighlight}
        />
      </div>
    );
  }
  return (
    <div
      data-essay-line-start={lineStartGlobal}
      style={{
        display: "flex",
        alignItems: "flex-start",
        lineHeight: 1.85,
        minHeight: "1.85em",
      }}
    >
      {useSpacer ? (
        <span aria-hidden style={{ width: PARAGRAPH_INDENT, flexShrink: 0 }} />
      ) : null}
      <div style={{ flex: 1, minWidth: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        <BlockText
          text={line}
          ranges={ranges}
          highlightBg={highlightBg}
          highlightTitle={highlightTitle}
          showSegmentIndex={showSegmentIndex}
          lineStartGlobal={lineStartGlobal}
          focusChar={focusChar}
          activeHighlightBg={activeHighlightBg}
          issueMarkHighlight={issueMarkHighlight}
        />
      </div>
    </div>
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
  scrollToChar = null,
  activeHighlightBg = "#ffd666",
  issueMarkHighlight,
  panelRef: panelRefProp,
  onPanelScroll,
  panelMinHeight,
  preserveOriginalLayout = false,
  referenceTemplate = false,
}: Props) {
  const layoutOpts = referenceTemplate ? false : preserveOriginalLayout;
  const lines = splitEssayLayoutLines(content, {
    inferPlainTitleAsHeading: referenceTemplate || !preserveOriginalLayout,
  });
  const innerPanelRef = useRef<HTMLDivElement>(null);
  const panelRef = panelRefProp ?? innerPanelRef;

  useEffect(() => {
    if (scrollToChar == null || scrollToChar < 0 || !panelRef.current) return;
    const line = lines.find((row) => scrollToChar >= row.start && scrollToChar < row.end);
    const targetStart = line?.start ?? scrollToChar;
    const el = panelRef.current.querySelector(`[data-essay-char-start="${targetStart}"]`);
    if (el instanceof HTMLElement) {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      return;
    }
    const rowEl = panelRef.current.querySelector(`[data-essay-line-start="${targetStart}"]`);
    rowEl?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [scrollToChar, lines, ranges]);

  return (
    <div
      ref={panelRef}
      onScroll={onPanelScroll}
      style={{
        marginTop: 8,
        padding: "12px 14px 20px",
        border: `1px solid ${borderColor}`,
        borderRadius: 8,
        background: panelBg,
        ...(panelMinHeight != null
          ? { minHeight: panelMinHeight, maxHeight: panelMinHeight }
          : { maxHeight: preserveOriginalLayout ? 560 : 480 }),
        overflowX: "hidden",
        overflowY: "auto",
        wordBreak: "break-word",
        fontSize: 14,
        lineHeight: 1.85,
        color: "rgba(0,0,0,0.88)",
        boxSizing: "border-box",
      }}
    >
      {!content.trim() ? (
        <Typography.Text type="secondary">{emptyLabel ?? "暂无正文"}</Typography.Text>
      ) : (
        lines.map((row, idx) => {
          if (row.kind === "empty") {
            return (
              <div
                key={`${row.start}-${idx}`}
                style={{ height: referenceTemplate ? 18 : 10 }}
                aria-hidden
              />
            );
          }

          const local = rangesOnLine(row.start, row.end, ranges);

          if (row.kind === "heading" && !layoutOpts) {
            const body = row.text.slice(row.markdownPrefixLen);
            const bodyRanges = highlightRangesForBody(local, row.markdownPrefixLen, body.length);
            const level = row.headingLevel ?? 1;
            return (
              <div
                key={`${row.start}-${idx}`}
                data-essay-line-start={row.start}
                style={{
                  ...(referenceTemplate ? REFERENCE_TITLE_STYLE : (HEADING_STYLE[level] ?? HEADING_STYLE[3])),
                  margin: referenceTemplate ? REFERENCE_TITLE_STYLE.margin : "0 0 4px",
                  whiteSpace: "pre-wrap",
                }}
              >
                <BlockText
                  text={body}
                  ranges={bodyRanges}
                  highlightBg={highlightBg}
                  highlightTitle={highlightTitle}
                  showSegmentIndex={showSegmentIndex}
                  lineStartGlobal={row.start + row.markdownPrefixLen}
                  focusChar={scrollToChar}
                  activeHighlightBg={activeHighlightBg}
                  issueMarkHighlight={issueMarkHighlight}
                />
              </div>
            );
          }

          if (row.kind === "heading" && layoutOpts && row.markdownPrefixLen > 0) {
            const body = row.text.slice(row.markdownPrefixLen);
            const bodyRanges = highlightRangesForBody(local, row.markdownPrefixLen, body.length);
            return (
              <BodyLine
                key={`${row.start}-${idx}`}
                line={body}
                lineStartGlobal={row.start + row.markdownPrefixLen}
                isParagraphStart={false}
                ranges={bodyRanges}
                highlightBg={highlightBg}
                highlightTitle={highlightTitle}
                showSegmentIndex={showSegmentIndex}
                focusChar={scrollToChar}
                activeHighlightBg={activeHighlightBg}
                issueMarkHighlight={issueMarkHighlight}
                preserveOriginalLayout
              />
            );
          }

          return (
            <div
              key={`${row.start}-${idx}`}
              style={
                referenceTemplate && row.isParagraphStart && row.kind === "body"
                  ? { marginTop: 10 }
                  : undefined
              }
            >
              <BodyLine
                line={row.text}
                lineStartGlobal={row.start}
                isParagraphStart={row.isParagraphStart}
                ranges={local}
                highlightBg={highlightBg}
                highlightTitle={highlightTitle}
                showSegmentIndex={showSegmentIndex}
                focusChar={scrollToChar}
                activeHighlightBg={activeHighlightBg}
                issueMarkHighlight={issueMarkHighlight}
                preserveOriginalLayout={layoutOpts}
              />
            </div>
          );
        })
      )}
    </div>
  );
}
