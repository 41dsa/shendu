import { Alert, Button, Result } from "antd";
import { Link } from "react-router-dom";

type Props = {
  /** 整页占位（报告、训练等）；否则为页内横幅 */
  variant?: "page" | "banner";
  /** 说明该功能名称，如「批改报告」 */
  feature?: string;
};

export default function ActivationRequiredNotice({ variant = "page", feature }: Props) {
  const featureHint = feature ? `「${feature}」` : "该功能";
  const description = (
    <>
      使用{featureHint}需要先激活账号。买断后在「激活」页兑换爱发电私信中的激活码；大作文批改还需在「AI 设置」中配置自备
      API Key。
    </>
  );

  if (variant === "banner") {
    return (
      <Alert
        type="warning"
        showIcon
        message="尚未激活"
        description={description}
        action={
          <Button size="small" type="primary">
            <Link to="/activate">去激活</Link>
          </Button>
        }
        style={{ marginBottom: 16 }}
      />
    );
  }

  return (
    <Result
      status="warning"
      title="账号尚未激活"
      subTitle={description}
      extra={[
        <Button type="primary" key="activate">
          <Link to="/activate">兑换激活码</Link>
        </Button>,
        <Button key="purchase">
          <Link to="/purchase">购买说明</Link>
        </Button>,
      ]}
    />
  );
}
