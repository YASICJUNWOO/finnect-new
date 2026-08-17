import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 서버 컴포넌트가 FastAPI 를 부른다. 브라우저는 API 주소를 모른다.
  // 원격 배포를 정할 때 이 값이 바뀐다 — ADR-0023 "안 정한 것".
  env: {
    FINNECT_API: process.env.FINNECT_API ?? "http://127.0.0.1:8100",
  },
};

export default nextConfig;
