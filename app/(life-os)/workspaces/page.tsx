import { WorkspacesView } from "@/components/life-os/workspaces-view";

export default async function WorkspacesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const initialView = typeof params.view === "string" ? params.view : "";

  return <WorkspacesView initialView={initialView} />;
}
