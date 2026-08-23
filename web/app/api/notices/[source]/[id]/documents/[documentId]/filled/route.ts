import { BASE, authHeaders } from "@/lib/api";

/** 초안을 넣어 **채운 원본 파일**을 브라우저에 넘기는 프록시 (plan/24 T-0155).
 *
 * 쓰기 화면의 오른쪽 단이 원본 대신 이것을 연다. 「들어가면 문서가 이미 써져
 * 있다」가 화면에서 참이 되는 자리다.
 *
 * **`attachments/[sha256]/file` 과 같은 규칙이다** — 토큰이 서버 전용이라 브라우저가
 * API 를 직접 못 부르고, 바이트를 그대로 흘리며, 상태 코드를 지어내지 않는다.
 *
 * **캐시를 안 건다.** 저쪽은 콘텐츠 주소라 내용이 안 바뀌지만 이 파일은 **초안이
 * 바뀌면 달라진다** — 사람이 글을 고치고 다시 열었을 때 옛 파일이 나오면 안 된다.
 *
 * **못 채운 칸 수를 헤더로 넘긴다.** 화면이 「N칸은 직접 채워 주세요」를 말해야
 * 하고, 조용히 남기면 사용자가 `000-0000-0000` 을 그대로 제출한다. */
export const dynamic = "force-dynamic";

export async function GET(
  req: Request,
  ctx: { params: Promise<{ source: string; id: string; documentId: string }> },
) {
  const { source, id, documentId } = await ctx.params;
  const company = new URL(req.url).searchParams.get("company") ?? "";
  if (!company) {
    return Response.json({ detail: "company 가 없어요" }, { status: 400 });
  }
  // **경로에 그대로 들어가는 값이다.** 숫자만 통과시킨다
  if (!/^\d{1,18}$/.test(documentId)) {
    return Response.json({ detail: "문서 식별자가 숫자가 아니에요" }, { status: 400 });
  }

  const path =
    `/api/notices/${encodeURIComponent(source)}/${encodeURIComponent(decodeURIComponent(id))}` +
    `/documents/${documentId}/filled?company=${encodeURIComponent(company)}`;

  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: authHeaders(),
      cache: "no-store",
    });

    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      return Response.json(
        { detail: detail || "채운 파일을 못 만들었어요" },
        { status: res.status },
      );
    }

    return new Response(res.body, {
      status: 200,
      headers: {
        "content-type": res.headers.get("content-type") ?? "application/octet-stream",
        "cache-control": "no-store",
        "x-finnect-filled": res.headers.get("x-finnect-filled") ?? "0",
        "x-finnect-left": res.headers.get("x-finnect-left") ?? "0",
      },
    });
  } catch (e) {
    console.error("채운 파일 프록시 실패", e);
    return Response.json({ detail: "채운 파일을 못 만들었어요" }, { status: 502 });
  }
}
