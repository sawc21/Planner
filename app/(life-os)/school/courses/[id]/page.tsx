import { redirect } from "next/navigation";

export default async function LegacyCoursePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/workspaces/${id}`);
}
