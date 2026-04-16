import { WorkspacesView } from "@/components/life-os/workspaces-view";

export default async function WorkspacesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const initialType = typeof params.type === "string" ? params.type : "";

  return <WorkspacesView initialType={initialType} />;
}
