import { Button, Card, Form, Input, InputNumber, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

type Profile = {
  id: string;
  exam_type: string;
  province: string;
  year: number;
  job_category: string;
};

export default function ExamProfilePage() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["exam-profile"],
    queryFn: () => api<Profile | null>("/exam-profiles"),
  });

  const save = useMutation({
    mutationFn: (body: Omit<Profile, "id">) =>
      api<Profile>("/exam-profiles", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => {
      message.success("已保存");
      qc.invalidateQueries({ queryKey: ["exam-profile"] });
    },
    onError: (e) => message.error(String(e)),
  });

  return (
    <Card title="考试目标">
      <Form
        layout="vertical"
        initialValues={
          data ?? { exam_type: "省考", province: "湖北", year: 2027, job_category: "县乡机关" }
        }
        key={data?.id ?? "new"}
        onFinish={(v) => save.mutate(v)}
      >
        <Form.Item name="exam_type" label="考试类型" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="province" label="省份" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="year" label="年份" rules={[{ required: true }]}>
          <InputNumber style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="job_category" label="职位类别" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={save.isPending}>
          保存
        </Button>
      </Form>
    </Card>
  );
}
