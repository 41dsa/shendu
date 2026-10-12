import { Tooltip, Typography } from "antd";
import { parseKeepReason } from "../utils/parseKeepReason";

type Props = {
  reason: string;
  keepProblem?: string;
  keepSolution?: string;
  solutionFallback?: string;
};

function ProblemHintTrigger() {
  return (
    <span
      role="img"
      aria-label="查看改进建议"
      style={{
        position: "absolute",
        top: -5,
        right: -11,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 14,
        height: 14,
        borderRadius: "50%",
        border: "1px solid rgba(0,0,0,0.35)",
        background: "#fff",
        color: "rgba(0,0,0,0.65)",
        fontSize: 10,
        fontWeight: 700,
        lineHeight: 1,
        cursor: "help",
        userSelect: "none",
      }}
    >
      !
    </span>
  );
}

export default function KeepSegmentReason({
  reason,
  keepProblem,
  keepSolution,
  solutionFallback,
}: Props) {
  const parsed = parseKeepReason(reason);
  const solution = (keepSolution || parsed.solution || solutionFallback || "").trim();

  const parenOpen = reason.indexOf("（");
  const parenClose = reason.indexOf("）");
  const hasParens = parenOpen >= 0 && parenClose > parenOpen;
  const innerFromReason =
    hasParens ? reason.slice(parenOpen + 1, parenClose).trim() : "";
  const problem = (keepProblem || parsed.problem || innerFromReason).trim();

  if (!hasParens || !problem || !solution) {
    return <Typography.Text type="secondary">{reason}</Typography.Text>;
  }

  const before = reason.slice(0, parenOpen);
  const after = reason.slice(parenClose + 1);

  return (
    <Typography.Text type="secondary">
      {before}
      <span style={{ position: "relative", display: "inline-block", verticalAlign: "baseline" }}>
        （{problem}）
        <Tooltip
          title={
            <span style={{ display: "block", whiteSpace: "pre-wrap", lineHeight: 1.55 }}>
              {solution}
            </span>
          }
          placement="topRight"
          mouseEnterDelay={0.12}
          mouseLeaveDelay={0}
          overlayStyle={{ maxWidth: 400 }}
        >
          <span style={{ position: "absolute", top: 0, right: 0, width: 14, height: 14, lineHeight: 0 }}>
            <ProblemHintTrigger />
          </span>
        </Tooltip>
      </span>
      {after}
    </Typography.Text>
  );
}
