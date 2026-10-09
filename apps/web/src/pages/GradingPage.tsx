import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Radio,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import { InboxOutlined, UploadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { UploadProps } from "antd";
import { api } from "../api/client";
import { showApiError } from "../api/errors";
import GradingJobPanel, { type GradingJobSubmissionSnapshot } from "../components/GradingJobPanel";
import GradingQueuePanel from "../components/GradingQueuePanel";
import ActivationRequiredNotice from "../components/ActivationRequiredNotice";
import { useEntitlement } from "../hooks/useEntitlement";

const DRAFT_KEY = "shendu_grading_draft_v1";

type GradingDraft = {
  mode: "bank" | "custom";
  questionId: string | null;
  userPrompt: string;
  userMaterial: string;
  answer: string;
};

type QuestionListItem = {
  id: string;
  title: string;
  score: number;
  word_min: number | null;
  word_max: number | null;
  exam: string | null;
  year: number | null;
  has_published_standard?: boolean;
};

type QuestionDetail = QuestionListItem & {
  prompt: string;
  reference_material: string | null;
};

function loadDraft(): GradingDraft | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as GradingDraft;
  } catch {
    return null;
  }
}

async function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("无法读取文件"));
    reader.readAsText(file, "UTF-8");
  });
}

export default function GradingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeJobId = searchParams.get("job");
  const initialQuestionId = searchParams.get("question");

  const qc = useQueryClient();
  const { data: ent } = useEntitlement();
  const initial = loadDraft();
  const [mode, setMode] = useState<"bank" | "custom">(initial?.mode ?? (initialQuestionId ? "bank" : "custom"));
  const [questionId, setQuestionId] = useState<string | null>(initial?.questionId ?? initialQuestionId);
  const [userPrompt, setUserPrompt] = useState(initial?.userPrompt ?? "");
  const [userMaterial, setUserMaterial] = useState(initial?.userMaterial ?? "");
  const [answer, setAnswer] = useState(initial?.answer ?? "");
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const restoredFormForJobRef = useRef<string | null>(null);

  const { data: catalog } = useQuery({
    queryKey: ["questions-catalog"],
    queryFn: () => api<QuestionListItem[]>("/questions?practice_only=true&limit=100"),
    enabled: !!ent?.licensed,
  });

  const { data: questionDetail } = useQuery({
    queryKey: ["question-detail", questionId],
    queryFn: () => api<QuestionDetail>(`/questions/${questionId}`),
    enabled: mode === "bank" && !!questionId,
  });

  const { data: activeJobForRestore } = useQuery({
    queryKey: ["grading-job", activeJobId],
    queryFn: () => api<{ status: string; submission?: GradingJobSubmissionSnapshot | null }>(
      `/grading-jobs/${activeJobId}`,
    ),
    enabled: !!activeJobId && !!ent?.licensed,
  });

  function applySubmissionToForm(snap: GradingJobSubmissionSnapshot) {
    const content = snap.content ?? "";
    if (snap.is_custom) {
      setMode("custom");
      setQuestionId(null);
      setUserPrompt(snap.user_prompt ?? "");
      setUserMaterial(snap.user_material ?? "");
      setAnswer(content);
      localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({
          mode: "custom",
          questionId: null,
          userPrompt: snap.user_prompt ?? "",
          userMaterial: snap.user_material ?? "",
          answer: content,
        } satisfies GradingDraft),
      );
      return;
    }
    setMode("bank");
    setQuestionId(snap.question_id);
    setAnswer(content);
    localStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({
        mode: "bank",
        questionId: snap.question_id,
        userPrompt: "",
        userMaterial: "",
        answer: content,
      } satisfies GradingDraft),
    );
  }

  useEffect(() => {
    if (!activeJobId) {
      restoredFormForJobRef.current = null;
      return;
    }
    if (!activeJobForRestore?.submission) return;
    if (activeJobForRestore.status !== "failed") return;
    if (restoredFormForJobRef.current === activeJobId) return;
    restoredFormForJobRef.current = activeJobId;
    applySubmissionToForm(activeJobForRestore.submission);
    message.info("已恢复该失败任务的作答内容，可修改后重新提交");
  }, [activeJobId, activeJobForRestore]);

  useEffect(() => {
    if (mode !== "bank" || !questionDetail) return;
    setUserPrompt(questionDetail.prompt);
    setUserMaterial(questionDetail.reference_material ?? "");
  }, [mode, questionDetail]);

  useEffect(() => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      const draft: GradingDraft = { mode, questionId, userPrompt, userMaterial, answer };
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    }, 800);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [mode, questionId, userPrompt, userMaterial, answer]);

  const wordMin = mode === "bank" && questionDetail?.word_min ? questionDetail.word_min : 800;
  const wordMax = mode === "bank" && questionDetail?.word_max ? questionDetail.word_max : 1200;

  const submit = useMutation({
    mutationFn: async () => {
      if (!answer.trim()) throw new Error("请填写或上传你的作文正文");
      if (mode === "bank") {
        if (!questionId) throw new Error("请选择题库题目");
        const sub = await api<{ id: string }>("/submissions", {
          method: "POST",
          body: JSON.stringify({
            question_id: questionId,
            content: answer,
            status: "draft",
          }),
        });
        return api<{ grading_job_id: string }>(`/submissions/${sub.id}/grade`, { method: "POST" });
      }
      const prompt = userPrompt.trim();
      if (!prompt) throw new Error("请填写题干与作答要求");
      const sub = await api<{ id: string }>("/submissions", {
        method: "POST",
        body: JSON.stringify({
          user_prompt: prompt,
          user_material: userMaterial.trim() || null,
          content: answer,
          status: "draft",
        }),
      });
      return api<{ grading_job_id: string }>(`/submissions/${sub.id}/grade`, { method: "POST" });
    },
    onSuccess: (res) => {
      message.success("已提交大作文批改，请在本页顶部查看进度");
      localStorage.removeItem(DRAFT_KEY);
      qc.invalidateQueries({ queryKey: ["grading-queue"] });
      setSearchParams({ job: res.grading_job_id });
    },
    onError: (e) => showApiError(e, "提交批改失败"),
  });

  const clearJob = () => setSearchParams({});

  const wordCount = answer.length;
  const needsKey = ent?.licensed && !ent?.has_primary_ai_key;

  const materialUpload: UploadProps = {
    accept: ".txt,.md,.text",
    showUploadList: false,
    beforeUpload: async (file) => {
      try {
        const text = await readTextFile(file);
        setUserMaterial((prev) => (prev ? `${prev}\n\n${text}` : text));
        message.success(`已导入材料：${file.name}`);
      } catch {
        message.error("材料文件读取失败");
      }
      return false;
    },
  };

  const answerUpload: UploadProps = {
    accept: ".txt,.md,.text",
    showUploadList: false,
    beforeUpload: async (file) => {
      try {
        const text = await readTextFile(file);
        setAnswer(text);
        message.success(`已导入作文：${file.name}`);
      } catch {
        message.error("作文文件读取失败");
      }
      return false;
    },
  };

  return (
    <>
      {activeJobId ? <GradingJobPanel jobId={activeJobId} onClose={clearJob} /> : null}

      {ent?.licensed ? (
        <GradingQueuePanel
          enabled={!!ent?.licensed}
          selectedJobId={activeJobId}
          onSelectJob={(id) => setSearchParams({ job: id })}
        />
      ) : null}

      {!ent?.licensed ? <ActivationRequiredNotice variant="banner" feature="大作文批改" /> : null}
      {needsKey ? (
        <Alert
          type="info"
          showIcon
          message="请先配置 AI Key"
          description="激活后需在「AI 设置」中填写 DeepSeek 或 OpenAI 兼容 API Key，才能提交批改。"
          action={
            <Button size="small" type="primary">
              <Link to="/settings/ai">去配置</Link>
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Radio.Group
            value={mode}
            onChange={(e) => {
              setMode(e.target.value);
              if (e.target.value === "custom") setQuestionId(null);
            }}
          >
            <Radio.Button value="bank">题库选题（已发布标准）</Radio.Button>
            <Radio.Button value="custom">自备题干与材料</Radio.Button>
          </Radio.Group>
          {mode === "bank" ? (
            <Select
              showSearch
              style={{ width: "100%", maxWidth: 640 }}
              placeholder="选择推荐真题 / 联调大作文"
              value={questionId ?? undefined}
              onChange={setQuestionId}
              optionFilterProp="label"
              options={(catalog ?? []).map((q) => ({
                value: q.id,
                label: q.title,
              }))}
            />
          ) : null}
          {mode === "bank" && questionDetail && (
            <Space wrap size={[8, 4]}>
              <Tag color="green">已发布考试标准</Tag>
              <Tag>{questionDetail.score} 分</Tag>
              <Tag>
                {wordMin}～{wordMax} 字
              </Tag>
              {questionDetail.exam && <Tag>{questionDetail.exam}</Tag>}
              {questionDetail.year && <Tag>{questionDetail.year}</Tag>}
            </Space>
          )}
          {mode === "custom" ? (
            <Typography.Text type="secondary">
              自备题使用默认维度 Rubric；题库题使用考试标准引擎已发布标准（更稳定）。
            </Typography.Text>
          ) : null}
        </Space>
      </Card>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card
            title="给定材料（可选）"
            size="small"
            extra={
              mode === "custom" ? (
                <Upload {...materialUpload}>
                  <Button size="small" icon={<UploadOutlined />}>
                    上传 .txt
                  </Button>
                </Upload>
              ) : null
            }
          >
            {mode === "bank" && !userMaterial.trim() ? (
              <Alert
                type="info"
                showIcon
                message="本题无给定材料"
                description="联调/真题库中该题未附带背景材料；请直接按右侧题干写作。批改仍使用本题已发布的维度标准。"
              />
            ) : (
              <Input.TextArea
                rows={mode === "bank" && userMaterial.trim() ? 10 : 10}
                value={userMaterial}
                onChange={(e) => setUserMaterial(e.target.value)}
                readOnly={mode === "bank"}
                placeholder="粘贴申论给定材料全文；无材料题可留空。"
              />
            )}
            {mode === "custom" && (
              <Upload.Dragger {...materialUpload} style={{ marginTop: 12 }}>
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">或拖拽材料文本文件到此处</p>
              </Upload.Dragger>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="题干与作答要求" size="small" style={{ marginBottom: 16 }}>
            <Input.TextArea
              rows={6}
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              readOnly={mode === "bank"}
              placeholder="粘贴题目要求…"
            />
          </Card>
          <Card
            title="我的作文"
            size="small"
            extra={
              <Upload {...answerUpload}>
                <Button size="small" icon={<UploadOutlined />}>
                  上传 .txt
                </Button>
              </Upload>
            }
          >
            <Input.TextArea
              rows={14}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="粘贴或输入完整大作文正文（含标题与分段）…"
            />
            <Typography.Text type={wordCount < wordMin ? "warning" : "secondary"}>
              {wordCount} 字（建议 {wordMin}～{wordMax} 字，以题干为准）
            </Typography.Text>
            <Button
              type="primary"
              block
              style={{ marginTop: 12 }}
              disabled={!ent?.licensed || !ent?.has_primary_ai_key}
              loading={submit.isPending}
              onClick={() => submit.mutate()}
            >
              提交 AI 批改
            </Button>
          </Card>
        </Col>
      </Row>
    </>
  );
}
