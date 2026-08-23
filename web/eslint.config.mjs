// eslint-config-next 16 은 flat config 를 그대로 낸다. FlatCompat 이 필요 없다.
import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

const config = [
  // `public/rhwp/**` 은 rhwp studio 미러본이다(`lib/documents.ts` 의 `STUDIO_URL`).
  // **우리 코드가 아니라 벤더 번들이라** 검사하면 안 된다 — 미니파이된 한 줄에서
  // 경고가 2,861개 나오고 그 안에 우리 것이 묻힌다.
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts", "public/rhwp/**"] },
  ...coreWebVitals,
  ...typescript,
];

export default config;
