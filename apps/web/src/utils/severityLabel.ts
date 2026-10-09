import type { CSSProperties } from "react";

const SEVERITY_ZH: Record<string, string> = {
  severe: "严重",
  moderate: "中等",
  minor: "轻微",
  high: "严重",
  medium: "中等",
  low: "轻微",
};

function normalizeSeverityKey(severity: string | null | undefined): string {
  if (!severity) return "moderate";
  return severity.trim().toLowerCase();
}

/** 报告/错题本中的 severity 展示为中文 */
export function severityLabel(severity: string | null | undefined): string {
  if (!severity) return "";
  return SEVERITY_ZH[normalizeSeverityKey(severity)] ?? severity;
}

/** 问题类型 Q 标签（与严重程度分色） */
export const issueTypeTagStyle: CSSProperties = {
  margin: 0,
  backgroundColor: "#fff7e6",
  borderColor: "#ffd591",
  color: "#d46b08",
  fontWeight: 600,
};

export type SeverityVisual = {
  style: CSSProperties;
  legend: string;
};

/** 严重程度：三色 + 对比度明显区分 */
export function severityVisual(severity: string | null | undefined): SeverityVisual {
  const key = normalizeSeverityKey(severity);
  if (key === "severe" || key === "high") {
    return {
      legend: "严重",
      style: {
        margin: 0,
        backgroundColor: "#ff4d4f",
        borderColor: "#cf1322",
        color: "#ffffff",
        fontWeight: 700,
        boxShadow: "0 0 0 1px rgba(207, 19, 34, 0.15)",
      },
    };
  }
  if (key === "minor" || key === "low") {
    return {
      legend: "轻微",
      style: {
        margin: 0,
        backgroundColor: "#f6ffed",
        borderColor: "#95de64",
        color: "#389e0d",
        fontWeight: 500,
      },
    };
  }
  return {
    legend: "中等",
    style: {
      margin: 0,
      backgroundColor: "#fff1b8",
      borderColor: "#fa8c16",
      color: "#ad4e00",
      fontWeight: 600,
    },
  };
}

/** @deprecated 使用 severityVisual */
export function severityTagColor(severity: string | null | undefined): string {
  const key = normalizeSeverityKey(severity);
  if (key === "severe" || key === "high") return "red";
  if (key === "minor" || key === "low") return "green";
  return "orange";
}
