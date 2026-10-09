import { Spin } from "antd";
import { Outlet } from "react-router-dom";
import ActivationRequiredNotice from "../components/ActivationRequiredNotice";
import { useEntitlement } from "../hooks/useEntitlement";

/** 未激活时展示明确引导，避免接口 403 导致空白或假空数据 */
export default function RequireLicense() {
  const { data: ent, isLoading } = useEntitlement();

  if (isLoading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
        <Spin size="large" tip="加载账号状态…" />
      </div>
    );
  }

  if (!ent?.licensed) {
    return <ActivationRequiredNotice variant="page" />;
  }

  return <Outlet />;
}
