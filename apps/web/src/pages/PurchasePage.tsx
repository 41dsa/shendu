import { Alert, Button, Card, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useEntitlement } from "../hooks/useEntitlement";

export default function PurchasePage() {
  const { data: ent } = useEntitlement();
  const { data: info } = useQuery({
    queryKey: ["purchase"],
    queryFn: () => api<{ afdian_plan_url: string; instructions: string }>("/purchase"),
  });

  return (
    <Card title="购买永久激活">
      {ent?.licensed ? (
        <Alert type="success" message="已激活" description={`SKU: ${ent.sku}`} showIcon />
      ) : (
        <>
          <Typography.Paragraph>{info?.instructions}</Typography.Paragraph>
          <Typography.Paragraph type="secondary">
            买断仅含软件功能；AI 批改需在「AI 设置」中配置自备 API Key 并自行向模型厂商充值。
          </Typography.Paragraph>
          <Button type="primary" href={info?.afdian_plan_url} target="_blank" rel="noreferrer">
            前往爱发电购买
          </Button>
          <Typography.Paragraph style={{ marginTop: 24 }}>
            已有激活码？<Link to="/activate">去兑换</Link>
          </Typography.Paragraph>
        </>
      )}
    </Card>
  );
}
