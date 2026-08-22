/// <reference types="react/canary" />

// `@types/react` 가 `ViewTransition` 을 `canary.d.ts` 안에만 선언하는데 tsconfig 도
// next-env 도 Next 가 주는 타입도 그것을 참조하지 않는다. 이 한 줄이 없으면
// `npm run typecheck` 가 깨진다.
//
// **`next-env.d.ts` 에 넣으면 안 된다.** `next dev` 가 그 파일을 다시 쓴다.
