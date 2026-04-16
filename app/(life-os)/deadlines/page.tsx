import { redirect } from "next/navigation";

export default function DeadlinesPage() {
  redirect("/assignments?scope=overdue");
}
