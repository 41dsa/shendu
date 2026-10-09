import { Alert, Button, Card, Col, Input, Row, Space, Typography, Upload, message } from "antd";
import { InboxOutlined, UploadOutlined } from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { UploadProps } from "antd";
import { api } from "../api/client";
import GradingJobPanel from "../components/GradingJobPanel";
import ActivationRequiredNotice from "../components/ActivationRequiredNotice";
import { useEntitlement } from "../hooks/useEntitlement";

const WORD_MIN = 800;
const WORD_MAX = 1200;

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

  const { data: ent } = useEntitlement();
  const [userPrompt, setUserPrompt] = useState("");
  const [userMaterial, setUserMaterial] = useState("");
  const [answer, setAnswer] = useState("");

  const submit = useMutation({
    mutationFn: async () => {
      const prompt = userPrompt.trim();
      if (!prompt) throw new Error("请填写题干与作答要求");
      if (!answer.trim()) throw new Error("请填写或上传你的作文正文");
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
      setSearchParams({ job: res.grading_job_id });
    },
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

      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        请粘贴或上传真实考试的<strong>给定材料</strong>、<strong>题干与作答要求</strong>，以及你的<strong>完整大作文</strong>。系统按标准大作文五维评分，不依赖内置题库。
      </Typography.Paragraph>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card
            title="给定材料（可选）"
            size="small"
            extra={
              <Upload {...materialUpload}>
                <Button size="small" icon={<UploadOutlined />}>
                  上传 .txt
                </Button>
              </Upload>
            }
          >
            <Input.TextArea
              rows={10}
              value={userMaterial}
              onChange={(e) => setUserMaterial(e.target.value)}
              placeholder="粘贴申论给定材料全文；无材料题可留空。"
            />
            <Upload.Dragger {...materialUpload} style={{ marginTop: 12 }}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">或拖拽材料文本文件到此处</p>
            </Upload.Dragger>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="题干与作答要求" size="small" style={{ marginBottom: 16 }}>
            <Input.TextArea
              rows={6}
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              placeholder="粘贴题目要求，如：结合给定材料，围绕××主题，自拟题目写一篇文章；字数 800～1200 字…"
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
            <Typography.Text type={wordCount < WORD_MIN ? "warning" : "secondary"}>
              {wordCount} 字（一般建议 {WORD_MIN}～{WORD_MAX} 字，以题干为准）
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
