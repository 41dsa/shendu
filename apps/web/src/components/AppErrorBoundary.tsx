import { Button, Result } from "antd";
import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: Error | null };

export default class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("AppErrorBoundary", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <Result
          status="error"
          title="页面出错"
          subTitle={this.state.error.message || "请刷新后重试"}
          extra={
            <Button type="primary" onClick={() => window.location.assign("/")}>
              返回首页
            </Button>
          }
        />
      );
    }
    return this.props.children;
  }
}
