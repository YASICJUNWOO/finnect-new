import type { MetadataRoute } from "next";

/** 설치 정보. `/manifest.webmanifest` 로 서브되고 Next 가 `<link>` 를 알아서 박는다.
 *
 * **서비스 워커가 없다**(ADR-0039). 그래서 이 앱은 홈 화면에 얹히고 크롬 없이 열리지만
 * **오프라인에서는 안 돈다.** 캐시를 붙이려면 낡은 데이터를 언제 버리는지부터 정해야 하고,
 * 그건 위키 마크다운을 저장하지 않기로 한 결정(뷰다)과 같은 자리에서 다시 얘기해야 한다.
 *
 * **`scope` 가 `/` 라서 운영 도구(`/admin`)도 앱 안에서 열린다.** 제품 라우트가
 * `/` · `/notices` · `/wiki` · `/documents` 로 흩어져 있어 공통 접두사가 `/` 밖에 없다 —
 * 좁히려면 제품 화면을 한 접두사 아래로 옮겨야 하고 그건 이 작업 밖이다(ADR-0039).
 *
 * 색 둘의 뜻이 다르다. `theme_color` 는 상태 막대에 깔리는 색이라 **바로 아래 있는
 * 상단 막대와 같아야 한다**(`--surface`). `background_color` 는 뜨는 동안의 바탕이라
 * 페이지 캔버스(`--canvas`)다. 결정은 `DESIGN.md` §12.3 에 있다.
 *
 * 값의 정본은 `web/app/tokens.css` 이고, 여기 리터럴로 적는 이유는 **매니페스트가 CSS 를
 * 못 읽기 때문이다.** **리터럴이 사는 곳이 셋이다** — 이 파일의 `theme_color` ·
 * `background_color`, 그리고 `app/layout.tsx` 의 `viewport.themeColor`. `--surface` 를
 * 고치면 **둘을 같이 고쳐야 한다**(이 파일과 layout.tsx). 처음에 이 주석이 '두 곳'이라고
 * 적었는데 세 곳이었고, 빠진 것이 하필 layout.tsx 였다.
 *
 * `orientation` 을 잠그지 않는다. 공고 상세와 위키 궤도는 눕혀서 보는 것이 나을 때가 있다. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "차차 — 지원사업",
    short_name: "차차",
    description: "맞는 공고를 골라 주고, 들어가면 문서가 이미 써져 있어요.",
    lang: "ko",
    dir: "ltr",
    categories: ["business", "productivity"],
    start_url: "/",
    scope: "/",
    display: "standalone",
    theme_color: "#fff",
    background_color: "#f7f7f8",
    // **용도마다 다른 파일이다. 같은 것을 두 번 적지 않는다.**
    //
    // 웹 표준은 `purpose: "any maskable"` 을 허용하고 Next 의 타입은 값 하나만 받지만
    // (`manifest-types.d.ts`), 애초에 한 파일로 둘을 겸할 수 없다 —
    //
    //   `maskable` OS 가 가운데 80% 만 남기고 깎는다. **모서리까지 꽉 차 있어야 한다**
    //   `any`      **아무도 안 깎는다.** 크롬 설치 창과 데스크톱 작업 표시줄이 그대로 그린다
    //
    // 그래서 `any` 에 각진 것을 주면 같은 순간 파비콘(`icon.svg`, 반경 22%)은 둥근데
    // 앱 아이콘만 검은 네모가 된다. `DESIGN.md` §12.1 이 '파비콘과 앱 아이콘이 갈린다'고
    // 적은 그 상태다. 반대로 `maskable` 을 둥글게 주면 네모 마스크를 쓰는 런처에서
    // 모서리가 비어 보인다. **둘 다 `tools/make-icons.py` 가 낸다.**
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      {
        src: "/icon-192-maskable.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/icon-512-maskable.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
