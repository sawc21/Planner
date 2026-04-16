import { WorkspaceDetailView } from "@/components/life-os/workspace-detail-view";

export default async function WorkspaceDetailPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  return <WorkspaceDetailView workspaceId={(await params).workspaceId} />;
}
