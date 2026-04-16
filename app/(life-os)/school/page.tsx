import { redirect } from "next/navigation";

export default function SchoolPage() {
  redirect("/workspaces?type=course");
}
