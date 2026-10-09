import {
  Alert,
  Button,
  Card,
  Collapse,
  Descriptions,
  Form,
  List,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Upload,
  message,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type ReactNode } from "react";
import { api } from "../../api/client";
import { apiUpload } from "../../api/upload";
import { showApiError } from "../../api/errors";

type DocRow = {
  id: string;
  title: string;
  source_level: string;
  exam: string;
  year: number | null;
  created_at: string | null;
};

type JobRow = {
  id: string;
  question_id: string;
  status: string;
  current_step: string | null;
  error_message: string | null;
  created_at: string | null;
  gen_mode?: string;
  cache_hit?: boolean;
  standard_confidence?: number;
  model_agreement?: number;
};

type AnnotationQuestionRow = {
  question_id: string;
  title: string;
  has_job: boolean;
  skip_reason?: string;
  essay_form_match?: boolean | null;
  keyword_recall?: number | null;
  standard_confidence?: number;
  duplicate_rate?: number;
};

type AnnotationMetrics = {
  rows_evaluated: number;
  form_match_rate: number | null;
  task_match_rate: number | null;
  keyword_recall_rate: number | null;
  targets_met: Record<string, boolean>;
  annotation_file: string;
  per_question: AnnotationQuestionRow[];
};

type MstdEaiMilestone = {
  essay_questions_published: number;
  published_standard_questions: number;
  ai_gold_samples: number;
  milestone_mstd_e_ai_passed: boolean;
  checks: Record<string, boolean>;
};

type JobDetail = JobRow & {
  steps: { step: string; detail: string; payload: Record<string, unknown>; at: string | null }[];
  document_ids: string[];
};

type QRow = { id: string; title: string };

type VersionRow = { version: number; status: string; is_active: boolean; published_at: string | null };

type RubricCriterion = {
  id: string;
  dimension_id: string;
  core: string;
  max_score?: number;
  confidence?: number;
};

export default function AdminStandardsPage() {
  const qc = useQueryClient();
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [manageQuestionId, setManageQuestionId] = useState<string | null>(null);

  const { data: docs } = useQuery({
    queryKey: ["admin-standards-docs"],
    queryFn: () => api<DocRow[]>("/admin/standards/documents"),
  });

  const { data: jobs, refetch: refetchJobs } = useQuery({
    queryKey: ["admin-standards-jobs"],
    queryFn: () => api<JobRow[]>("/admin/standards/jobs"),
    refetchInterval: (q) => {
      const rows = q.state.data ?? [];
      const running = rows.some((j) => j.status === "pending" || j.status === "running");
      return running ? 3000 : false;
    },
  });

  const { data: questions } = useQuery({
    queryKey: ["admin-questions"],
    queryFn: () => api<QRow[]>("/admin/questions"),
  });

  const { data: jobDetail, isFetching: jobLoading } = useQuery({
    queryKey: ["admin-standards-job", selectedJobId],
    queryFn: () => api<JobDetail>(`/admin/standards/jobs/${selectedJobId}`),
    enabled: !!selectedJobId,
    refetchInterval: (q) => {
      const st = q.state.data?.status;
      return st === "pending" || st === "running" ? 2000 : false;
    },
  });

  const { data: annotationMetrics, refetch: refetchMetrics } = useQuery({
    queryKey: ["admin-standards-annotation-metrics"],
    queryFn: () => api<AnnotationMetrics>("/admin/standards/annotation-metrics"),
  });

  const { data: mstdEai, refetch: refetchMstdEai } = useQuery({
    queryKey: ["admin-mstd-e-ai-milestone"],
    queryFn: () => api<MstdEaiMilestone>("/admin/mstd-e-ai-milestone"),
  });

  const { data: versions, refetch: refetchVersions } = useQuery({
    queryKey: ["admin-standards-versions", manageQuestionId],
    queryFn: () => api<VersionRow[]>(`/admin/standards/questions/${manageQuestionId}/versions`),
    enabled: !!manageQuestionId,
  });

  const uploadMut = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("title", file.name);
      fd.append("source_level", "B");
      return apiUpload<{ id: string; parse_quality?: string }>("/admin/standards/documents/upload", fd);
    },
    onSuccess: () => {
      message.success("资料已上传");
      qc.invalidateQueries({ queryKey: ["admin-standards-docs"] });
    },
    onError: showApiError,
  });

  const createJobMut = useMutation({
    mutationFn: (v: { question_id: string; document_ids: string[] }) =>
      api<{ id: string }>("/admin/standards/jobs", {
        method: "POST",
        body: JSON.stringify(v),
      }),
    onSuccess: (res) => {
      message.success("标准生成任务已创建");
      setSelectedJobId(res.id);
      refetchJobs();
    },
    onError: showApiError,
  });

  const publishMut = useMutation({
    mutationFn: ({ jobId, force }: { jobId: string; force?: boolean }) =>
      api(`/admin/standards/jobs/${jobId}/publish${force ? "?force=true" : ""}`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: () => {
      message.success("标准已发布");
      qc.invalidateQueries({ queryKey: ["admin-standards-jobs"] });
      if (selectedJobId) qc.invalidateQueries({ queryKey: ["admin-standards-job", selectedJobId] });
      if (jobDetail?.question_id) {
        setManageQuestionId(jobDetail.question_id);
        refetchVersions();
      }
    },
    onError: showApiError,
  });

  const rollbackMut = useMutation({
    mutationFn: (v: { question_id: string; version: number }) =>
      api(`/admin/standards/questions/${v.question_id}/rollback?version=${v.version}`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: () => {
      message.success("已回滚到指定版本");
      refetchVersions();
    },
    onError: showApiError,
  });

  const validateStep = jobDetail?.steps?.filter((s) => s.step === "validate").pop();
  const validatePayload = validateStep?.payload as
    | {
        overall_passed?: boolean;
        standard_confidence?: number;
        confidence_band?: string;
        reference_coverage_detail?: { coverage_ratio?: number; source?: string };
      }
    | undefined;

  const ingestStep = jobDetail?.steps?.filter((s) => s.step === "ingest").pop()?.payload as
    | { cache_hit?: boolean; input_fingerprint?: string; mode?: string }
    | undefined;

  const rubricCandidatesStep = jobDetail?.steps?.filter((s) => s.step === "rubric_candidates").pop()?.payload as
    | { model_agreement?: number; cache_hit?: boolean }
    | undefined;

  const rubricMerged = jobDetail?.steps?.filter((s) => s.step === "rubric_merged").pop()?.payload as
    | { dimensions?: { id: string; label: string; max_score: number }[]; criteria?: RubricCriterion[] }
    | undefined;

  const rubricTableRows = useMemo(() => {
    const criteria = rubricMerged?.criteria ?? [];
    const dimMap = Object.fromEntries((rubricMerged?.dimensions ?? []).map((d) => [d.id, d.label]));
    return criteria.map((c) => ({
      key: c.id,
      dimension: dimMap[c.dimension_id] ?? c.dimension_id,
      core: c.core,
      max_score: c.max_score,
      confidence: c.confidence,
    }));
  }, [rubricMerged]);

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Alert
        type={mstdEai?.milestone_mstd_e_ai_passed ? "success" : "info"}
        showIcon
        message={
          mstdEai?.milestone_mstd_e_ai_passed
            ? "M-STD-E-AI 里程碑已通过（纯 AI 自洽）"
            : "AI 考试标准引擎 · 纯 AI 模式（DEC-06～08）"
        }
        description={
          mstdEai
            ? `已发布标准 ${mstdEai.published_standard_questions} 题 · AI 金标 ${mstdEai.ai_gold_samples} 条。CLI: run_pure_ai_pipeline.py`
            : "上传资料 → 生成 → 验证 → 自动发布。详见 纯AI运行手册.md"
        }
        action={
          <Button size="small" onClick={() => refetchMstdEai()}>
            刷新里程碑
          </Button>
        }
      />

      <Card title="资料上传（M1/M2）" size="small">
        <Upload
          maxCount={1}
          beforeUpload={(file) => {
            uploadMut.mutate(file);
            return false;
          }}
          showUploadList={false}
        >
          <Button loading={uploadMut.isPending}>选择 TXT / PDF / DOCX 上传</Button>
        </Upload>
        <List
          style={{ marginTop: 16 }}
          size="small"
          dataSource={docs ?? []}
          renderItem={(d) => (
            <List.Item>
              <Tag>{d.source_level}</Tag> {d.title}{" "}
              <TypographyMuted>{d.id.slice(0, 8)}…</TypographyMuted>
            </List.Item>
          )}
        />
      </Card>

      <Card title="创建标准生成任务" size="small">
        <Form
          layout="inline"
          onFinish={(v) =>
            createJobMut.mutate({
              question_id: v.question_id,
              document_ids: v.document_ids ?? [],
            })
          }
        >
          <Form.Item name="question_id" rules={[{ required: true, message: "请选择题号" }]}>
            <Select
              style={{ minWidth: 320 }}
              placeholder="选择大作文题目"
              options={(questions ?? []).map((q) => ({ value: q.id, label: q.title }))}
            />
          </Form.Item>
          <Form.Item name="document_ids">
            <Select
              mode="multiple"
              style={{ minWidth: 240 }}
              placeholder="关联资料（可选）"
              options={(docs ?? []).map((d) => ({ value: d.id, label: d.title }))}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={createJobMut.isPending}>
              生成标准
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card
        title="AI 自洽指标（STD-704）"
        size="small"
        extra={
          <Button size="small" onClick={() => refetchMetrics()}>
            刷新
          </Button>
        }
      >
        {annotationMetrics ? (
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="标注行">{annotationMetrics.rows_evaluated}</Descriptions.Item>
            <Descriptions.Item label="数据文件">
              {annotationMetrics.annotation_file.split("/").slice(-2).join("/")}
            </Descriptions.Item>
            <Descriptions.Item label="命题形式">
              {annotationMetrics.form_match_rate != null
                ? `${(annotationMetrics.form_match_rate * 100).toFixed(1)}% ${annotationMetrics.targets_met?.form_match_rate ? "✓" : "✗"}`
                : "—"}
            </Descriptions.Item>
            <Descriptions.Item label="关键词召回">
              {annotationMetrics.keyword_recall_rate != null
                ? `${(annotationMetrics.keyword_recall_rate * 100).toFixed(1)}% ${annotationMetrics.targets_met?.keyword_recall_rate ? "✓" : "✗"}`
                : "N/A"}
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <span>加载中…</span>
        )}
        {(annotationMetrics?.per_question?.length ?? 0) > 0 && (
          <Table
            size="small"
            style={{ marginTop: 12 }}
            rowKey="question_id"
            pagination={{ pageSize: 8, showSizeChanger: false }}
            dataSource={annotationMetrics!.per_question}
            columns={[
              { title: "题目", dataIndex: "title", ellipsis: true },
              { title: "ID", dataIndex: "question_id", width: 120, ellipsis: true },
              {
                title: "Job",
                dataIndex: "has_job",
                width: 64,
                render: (ok: boolean) => (ok ? <Tag color="green">有</Tag> : <Tag>无</Tag>),
              },
              {
                title: "形式",
                dataIndex: "essay_form_match",
                width: 56,
                render: (v: boolean | null | undefined) =>
                  v === true ? "✓" : v === false ? "✗" : "—",
              },
              {
                title: "词召回",
                dataIndex: "keyword_recall",
                width: 72,
                render: (v: number | null | undefined) =>
                  v != null ? `${(v * 100).toFixed(0)}%` : "—",
              },
              {
                title: "置信度",
                dataIndex: "standard_confidence",
                width: 72,
                render: (v: number | undefined) => (v != null ? Number(v).toFixed(2) : "—"),
              },
            ]}
          />
        )}
      </Card>

      <Card title="已发布标准 · 版本与回滚" size="small">
        <Select
          style={{ minWidth: 360, marginBottom: 12 }}
          placeholder="选择题号查看版本"
          value={manageQuestionId ?? undefined}
          onChange={(v) => setManageQuestionId(v)}
          options={(questions ?? []).map((q) => ({ value: q.id, label: q.title }))}
          allowClear
        />
        <Table
          rowKey="version"
          size="small"
          pagination={false}
          dataSource={versions ?? []}
          columns={[
            { title: "版本", dataIndex: "version" },
            { title: "状态", dataIndex: "status", render: (s) => <Tag>{s}</Tag> },
            {
              title: "生效",
              dataIndex: "is_active",
              render: (a) => (a ? <Tag color="green">当前</Tag> : null),
            },
            {
              title: "发布",
              dataIndex: "published_at",
              render: (t) => (t ? new Date(t).toLocaleString() : ""),
            },
            {
              title: "操作",
              render: (_, row) =>
                row.is_active ? null : (
                  <Popconfirm
                    title={`回滚到 v${row.version}？`}
                    onConfirm={() =>
                      manageQuestionId &&
                      rollbackMut.mutate({ question_id: manageQuestionId, version: row.version })
                    }
                  >
                    <Button size="small" loading={rollbackMut.isPending}>
                      回滚
                    </Button>
                  </Popconfirm>
                ),
            },
          ]}
        />
      </Card>

      <Card title="标准任务" size="small">
        <Table
          rowKey="id"
          size="small"
          dataSource={jobs ?? []}
          pagination={{ pageSize: 10 }}
          onRow={(row) => ({
            onClick: () => setSelectedJobId(row.id),
            style: { cursor: "pointer" },
          })}
          columns={[
            { title: "状态", dataIndex: "status", render: (s) => <Tag>{s}</Tag> },
            { title: "题目", dataIndex: "question_id", ellipsis: true },
            {
              title: "模式",
              dataIndex: "gen_mode",
              width: 64,
              render: (m, row) => (
                <Space size={4}>
                  <Tag>{m ?? "—"}</Tag>
                  {row.cache_hit ? <Tag color="blue">缓存</Tag> : null}
                </Space>
              ),
            },
            {
              title: "置信度",
              dataIndex: "standard_confidence",
              width: 72,
              render: (v) => (v != null ? Number(v).toFixed(2) : "—"),
            },
            { title: "步骤", dataIndex: "current_step" },
            { title: "错误", dataIndex: "error_message", ellipsis: true },
            {
              title: "创建",
              dataIndex: "created_at",
              render: (t) => (t ? new Date(t).toLocaleString() : ""),
            },
          ]}
        />
      </Card>

      <Modal
        open={!!selectedJobId}
        onCancel={() => setSelectedJobId(null)}
        width={920}
        title={`任务详情 ${selectedJobId?.slice(0, 8)}…`}
        footer={
          jobDetail?.status === "validated" ? (
            <Space>
              <Button
                onClick={() => selectedJobId && publishMut.mutate({ jobId: selectedJobId })}
                type="primary"
                loading={publishMut.isPending}
              >
                发布标准
              </Button>
              {(validatePayload?.standard_confidence ?? 1) < 0.85 && (
                <Popconfirm
                  title="置信度低于 0.85，确定强制发布？"
                  onConfirm={() => selectedJobId && publishMut.mutate({ jobId: selectedJobId, force: true })}
                >
                  <Button danger loading={publishMut.isPending}>
                    强制发布
                  </Button>
                </Popconfirm>
              )}
            </Space>
          ) : null
        }
      >
        {jobLoading && !jobDetail ? (
          <span>加载中…</span>
        ) : jobDetail ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="状态">{jobDetail.status}</Descriptions.Item>
              <Descriptions.Item label="题目">{jobDetail.question_id}</Descriptions.Item>
              {ingestStep && (
                <>
                  <Descriptions.Item label="生成模式">{ingestStep.mode ?? "—"}</Descriptions.Item>
                  <Descriptions.Item label="LLM 缓存">
                    {ingestStep.cache_hit ? <Tag color="blue">命中</Tag> : <Tag>未命中</Tag>}
                  </Descriptions.Item>
                </>
              )}
              {validatePayload && (
                <>
                  <Descriptions.Item label="验证">
                    {validatePayload.overall_passed ? <Tag color="green">通过</Tag> : <Tag color="red">未通过</Tag>}
                  </Descriptions.Item>
                  <Descriptions.Item label="置信度">
                    {validatePayload.standard_confidence ?? "—"} ({validatePayload.confidence_band ?? ""})
                  </Descriptions.Item>
                  <Descriptions.Item label="参考覆盖">
                    {validatePayload.reference_coverage_detail?.coverage_ratio ?? "—"}{" "}
                    {validatePayload.reference_coverage_detail?.source
                      ? `(${validatePayload.reference_coverage_detail.source})`
                      : ""}
                  </Descriptions.Item>
                  <Descriptions.Item label="双模型一致率">
                    {rubricCandidatesStep?.model_agreement != null
                      ? rubricCandidatesStep.model_agreement
                      : rubricCandidatesStep?.cache_hit
                        ? "（缓存）"
                        : "—"}
                  </Descriptions.Item>
                </>
              )}
            </Descriptions>
            {rubricTableRows.length > 0 && (
              <Table
                size="small"
                pagination={false}
                title={() => "Rubric 准则预览"}
                dataSource={rubricTableRows}
                columns={[
                  { title: "维度", dataIndex: "dimension", width: 120 },
                  { title: "准则", dataIndex: "core" },
                  { title: "满分", dataIndex: "max_score", width: 72 },
                  { title: "置信度", dataIndex: "confidence", width: 88 },
                ]}
              />
            )}
            <Collapse
              items={(jobDetail.steps ?? []).map((s, i) => ({
                key: String(i),
                label: `${s.step} · ${s.detail}`,
                children: (
                  <pre style={{ maxHeight: 240, overflow: "auto", fontSize: 12 }}>
                    {JSON.stringify(s.payload, null, 2)}
                  </pre>
                ),
              }))}
            />
          </Space>
        ) : null}
      </Modal>
    </Space>
  );
}

function TypographyMuted({ children }: { children: ReactNode }) {
  return <span style={{ color: "#999", marginLeft: 8 }}>{children}</span>;
}
