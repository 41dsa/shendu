import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import AppErrorBoundary from "./components/AppErrorBoundary";
import { showApiError } from "./api/client";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    mutations: {
      onError: (error) => showApiError(error),
    },
    queries: {
      retry: (failureCount, error) => {
        const code = String(error);
        if (code.includes("LICENSE_REQUIRED") || code.includes("AI_KEY_REQUIRED")) return false;
        return failureCount < 1;
      },
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: "#1677ff", borderRadius: 10 } }}>
        <AppErrorBoundary>
          <App />
        </AppErrorBoundary>
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
