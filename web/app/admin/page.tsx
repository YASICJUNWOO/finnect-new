import { redirect } from "next/navigation";

/** `/admin` 은 공고 목록으로 보낸다. 옛 Jinja2 `/` 가 `/notices` 로 보낸 것과 같다. */
export default function AdminIndex() {
  redirect("/admin/notices");
}
