import { Alert, Button, Card, Form, Select, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { api } from "../api/client";

type Profile = {
  id: string;
  exam_type: string;
  province: string;
  year: number;
  job_category: string;
  summary?: string | null;
  mapped_bank_exam?: string | null;
  mapped_bank_year?: number | null;
};

type FormOptions = {
  exam_types: { value: string; label: string }[];
  guokao_jobs: { value: string; label: string }[];
  shengkao_jobs: { value: string; label: string }[];
  provinces: string[];
  years: number[];
};

function normalizeJobCategory(
  examType: string,
  jobCategory: string | undefined,
  options: FormOptions | undefined,
): string {
  if (examType === "guokao") {
    const valid = (options?.guokao_jobs ?? []).map((j) => j.value);
    if (jobCategory && valid.includes(jobCategory)) return jobCategory;
    return "shidi";
  }
  const valid = (options?.shengkao_jobs ?? []).map((j) => j.value);
  if (jobCategory && valid.includes(jobCategory)) return jobCategory;
  return "xiangzhen";
}

export default function ExamProfilePage() {
  const qc = useQueryClient();
  const [form] = Form.useForm();

  const { data: options } = useQuery({
    queryKey: ["exam-profile-options"],
    queryFn: () => api<FormOptions>("/exam-profiles/options"),
  });

  const { data } = useQuery({
    queryKey: ["exam-profile"],
    queryFn: () => api<Profile | null>("/exam-profiles"),
  });

  const examType = Form.useWatch("exam_type", form) ?? data?.exam_type ?? "shengkao";

  const save = useMutation({
    mutationFn: (body: Omit<Profile, "id" | "summary" | "mapped_bank_exam" | "mapped_bank_year">) =>
      api<Profile>("/exam-profiles", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: (res) => {
      message.success("已保存");
      qc.invalidateQueries({ queryKey: ["exam-profile"] });
      qc.invalidateQueries({ queryKey: ["questions-recommended"] });
      if (res.summary) {
        message.info(`推荐卷种：${res.mapped_bank_exam ?? "—"} · ${res.mapped_bank_year ?? ""}`);
      }
    },
    onError: (e) => message.error(String(e)),
  });

  const initial = useMemo(() => {
    const base = data ?? {
      exam_type: "shengkao",
      province: "湖北",
      year: options?.years?.[0] ?? 2027,
      job_category: "xiangzhen",
    };
    const examType = base.exam_type || "shengkao";
    return {
      ...base,
      exam_type: examType,
      province: examType === "guokao" ? "" : base.province || "湖北",
      job_category: normalizeJobCategory(examType, base.job_category, options),
    };
  }, [data, options]);

  return (
    <Card title="考试目标">
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="规范卷种"
        description="选择考试类型与职位层级后，系统会映射到题库卷种（如「国考市地级」「湖北省考」），用于首页推荐与练习匹配。"
      />
      <Form
        form={form}
        layout="vertical"
        initialValues={initial}
        key={data?.id ?? "new"}
        onFinish={(v) =>
          save.mutate({
            ...v,
            province: v.exam_type === "guokao" ? "" : v.province,
          })
        }
        onValuesChange={(changed, all) => {
          if (!("exam_type" in changed)) return;
          const et = changed.exam_type as string;
          if (et === "guokao") {
            form.setFieldsValue({
              province: "",
              job_category: normalizeJobCategory("guokao", all.job_category, options),
            });
          } else if (et === "shengkao") {
            form.setFieldsValue({
              province: all.province || "湖北",
              job_category: normalizeJobCategory("shengkao", all.job_category, options),
            });
          }
        }}
      >
        <Form.Item name="exam_type" label="考试类型" rules={[{ required: true }]}>
          <Select
            options={(options?.exam_types ?? []).map((o) => ({ value: o.value, label: o.label }))}
          />
        </Form.Item>
        {examType === "shengkao" && (
          <Form.Item name="province" label="省份" rules={[{ required: true }]}>
            <Select
              showSearch
              optionFilterProp="label"
              options={(options?.provinces ?? []).map((p) => ({ value: p, label: p }))}
            />
          </Form.Item>
        )}
        {examType === "guokao" && (
          <Form.Item name="job_category" label="卷种 / 职位层级" rules={[{ required: true }]}>
            <Select options={options?.guokao_jobs ?? []} />
          </Form.Item>
        )}
        {examType === "shengkao" && (
          <Form.Item name="job_category" label="职位类别" rules={[{ required: true }]}>
            <Select options={options?.shengkao_jobs ?? []} />
          </Form.Item>
        )}
        <Form.Item name="year" label="目标年份" rules={[{ required: true }]}>
          <Select options={(options?.years ?? []).map((y) => ({ value: y, label: String(y) }))} />
        </Form.Item>
        {data?.mapped_bank_exam && (
          <Alert
            type="success"
            showIcon
            style={{ marginBottom: 16 }}
            message={`当前映射：${data.mapped_bank_exam} · ${data.mapped_bank_year ?? data.year}`}
            description={data.summary ?? undefined}
          />
        )}
        <Button type="primary" htmlType="submit" loading={save.isPending}>
          保存
        </Button>
      </Form>
    </Card>
  );
}
