import { Tooltip } from "antd";
import type { CSSProperties } from "react";
import { EDIT_FRAGMENT_MARK_STYLE } from "./EssayHighlightView";

const MARK_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: 15,
  height: 15,
  marginLeft: 4,
  verticalAlign: "0.12em",
  borderRadius: "50%",
  border: "1px solid rgba(0, 0, 0, 0.28)",
  fontSize: 10,
  fontWeight: 700,
  lineHeight: 1,
  color: "rgba(0, 0, 0, 0.5)",
  cursor: "help",
  userSelect: "none",
  flexShrink: 0,
};

const MARK_ON_DARK: CSSProperties = {
  ...EDIT_FRAGMENT_MARK_STYLE,
  background: "rgba(255, 214, 102, 0.35)",
  color: "#fff",
};

type Props = {
  content: string;
  placement?: "top" | "topLeft" | "topRight";
};

/** 悬停只展示完整改写句，不展示「（原：…）」对照行 */
function extractFullRewriteExample(raw: string): string {
  let text = raw.trim();
  if (!text) return "";
  text = text
    .replace(/^改写示例[：:]\s*/, "")
    .replace(/^续写示例[，,][^：:]*[：:]\s*/, "")
    .replace(/^可改为[：:]\s*/, "");
  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("（原：") && !l.startsWith("(原："));
  text = lines.join("");
  const quoted = text.match(/「([^」]+)」/);
  if (quoted?.[1]?.trim()) return quoted[1].trim();
  return text.replace(/^「|」$/g, "").trim();
}

function SolutionExampleBody({ text }: { text: string }) {
  const example = extractFullRewriteExample(text);
  if (!example) return null;

  return (
    <div
      style={{
        maxWidth: 360,
        fontSize: 13,
        lineHeight: 1.75,
        whiteSpace: "pre-wrap",
        color: "rgba(255,255,255,0.92)",
      }}
    >
      <span>改写示例：仅供参考：</span>
      <mark style={MARK_ON_DARK}>「{example}」</mark>
    </div>
  );
}

/** 说明文字末尾的小圆圈感叹号，悬停展示修改示例 */
export default function IssueSolutionHintMark({ content, placement = "top" }: Props) {
  const text = content.trim();
  if (!text) return null;
  const example = extractFullRewriteExample(text);
  if (!example || example.length < 8) return null;

  return (
    <Tooltip
      trigger="hover"
      placement={placement}
      color="rgba(0, 0, 0, 0.88)"
      mouseEnterDelay={0.15}
      overlayStyle={{ maxWidth: 380 }}
      title={<SolutionExampleBody text={text} />}
    >
      <span role="img" aria-label="改写示例，仅供参考" style={MARK_STYLE} onClick={(e) => e.stopPropagation()}>
        !
      </span>
    </Tooltip>
  );
}
