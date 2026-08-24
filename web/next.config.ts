import type { NextConfig } from "next";

const API = process.env.FINNECT_API ?? "http://127.0.0.1:8100";

/** **불변 배포 URL 을 잡아낸다.**
 *
 * `finnect-<해시>-<팀>.vercel.app` 은 그 배포에 못 박힌 주소다. `FINNECT_API` 에 넣으면
 * 그날은 돌고, **API 에 새 경로가 생겨도 웹은 영원히 못 본다.**
 *
 * 2026-08-17 이걸로 넘어졌다. 운영 화면을 올렸는데 `/admin/*` 이 500 이었고 원인이
 * "웹이 부르는 옛 배포에는 그 경로가 없다"였다. **`/` 는 정상이라 늦게 잡혔다** —
 * `/api/notices` 는 옛 배포에도 있었기 때문이다.
 *
 * 그래서 **빌드 로그에 남긴다.** 런타임 404 보다 여기가 원인에 가깝다.
 *
 * **막지 않고 경고만 한다.** 여기서 빌드를 죽이면 값을 고치기 전까지 아무것도 안 올라가고,
 * 그 상태가 지금 문제보다 나쁘다. 프리뷰에서 일부러 한 배포를 가리키는 경우도 있다. */
const PINNED = /^https?:\/\/[a-z0-9-]+-[a-z0-9]{9}-[a-z0-9-]+\.vercel\.app/i;

if (PINNED.test(API)) {
  console.warn(
    [
      "",
      "  ⚠ FINNECT_API 가 불변 배포 URL 을 가리킨다.",
      `      ${API}`,
      "",
      "  이 주소는 그 배포에 못 박혀 있어서 API 에 새 경로가 생겨도 안 보인다.",
      "  프로젝트 프로덕션 도메인을 쓴다 — https://finnect-api.vercel.app",
      "  자세한 것은 docs/deploy.md 5단계.",
      "",
    ].join("\n"),
  );
}

const nextConfig: NextConfig = {
  // 서버 컴포넌트가 FastAPI 를 부른다. 브라우저는 API 주소를 모른다.
  //
  // **`env` 는 빌드 시점에 문자열로 박아 넣는다.** 그래서 이 값을 고치면
  // 웹을 다시 빌드해야 하고, 환경변수만 갈면 옛 값이 그대로 산다.
  env: {
    FINNECT_API: API,
  },
  // `FINNECT_ADMIN` 이 여기 있었다. 운영 화면이 같은 앱으로 들어와서(ADR-0027)
  // 링크가 상대 경로가 됐고 주소를 줄 자리가 없어졌다.

  /** rhwp studio 미러본을 오래 캐시한다(`lib/documents.ts` 의 `STUDIO_URL`).
   *
   * **`public/` 의 기본값이 `max-age=0` 이다.** 파일 이름에 해시가 없는 것이 섞여
   * 있어서 Next 가 일괄로 그렇게 준다. 그러면 쓰기 화면에 들어갈 때마다 WASM
   * 2,947KB 와 웹폰트 3,255KB 를 재검증한다.
   *
   * **원본은 이 일을 서비스 워커가 했다**(`sw.js` 의 `wasm-cache` · 30일). 미러본에서
   * 그 SW 를 껐으므로([ADR-0039](../docs/adr/0039-설치되는-앱으로-만들되-서비스-워커는-안-붙인다.md))
   * 캐시를 여기서 준다.
   *
   * **`immutable` 을 `assets`·`fonts` 에만 준다.** 저기는 이름에 해시가 있거나
   * (`index-s2CVbjxO.js`) 갈릴 일이 없는 폰트다. `index.html` 은 그 해시를 가리키는
   * 쪽이라 같이 굳히면 **미러본을 갱신해도 옛 자산을 계속 부른다.** */
  async headers() {
    return [
      {
        source: "/rhwp/:dir(assets|fonts)/:file*",
        headers: [
          { key: "cache-control", value: "public, max-age=31536000, immutable" },
        ],
      },
      /** 시연 신청서(`public/demo/`)의 파일 이름을 **응답이 정하지 않게 한다.**
       *
       * S4 머리줄의 「내려받기」가 `<a download="…">` 로 `파일명_회사이름.hwp` 를
       * 적는데, **응답에 `filename` 이 있으면 그쪽이 이긴다**(브라우저 규칙).
       * Vercel 이 `public/` 의 `.hwp` 에 `content-disposition: inline;
       * filename="narin-application.hwp"` 를 붙여서, 로컬에서는 이름이 맞고
       * **배포본에서만 `narin-application.hwp` 로 떨어졌다**(실측 2026-08-25).
       *
       * `filename` 없는 `inline` 으로 덮는다 — 뷰어는 이 파일을 `fetch` 로 받으므로
       * 이 값이 화면에 영향을 주지 않는다. **`attachment` 로 안 바꾼다**: 그러면
       * 주소로 직접 열었을 때도 받아지고, 그건 이 헤더가 할 말이 아니다. */
      {
        source: "/demo/:file*",
        headers: [{ key: "content-disposition", value: "inline" }],
      },
    ];
  },
};

export default nextConfig;
