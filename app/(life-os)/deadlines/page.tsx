import { redirect } from "next/navigation";

export default async function DeadlinesPage({
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  redirect("/tasks?scope=overdue");
}
