import { render } from "@testing-library/react";

import { buildSeedLifeOsData } from "@/lib/life-os/mock-data";
import { LifeOsProvider } from "@/lib/life-os/state";
import type { LifeOsSnapshot } from "@/lib/life-os/types";

export const REFERENCE_DATE = new Date("2026-04-16T09:00:00-05:00");

export function renderWithLifeOs(
  ui: React.ReactElement,
  { data = buildSeedLifeOsData(REFERENCE_DATE) }: { data?: LifeOsSnapshot } = {},
) {
  return render(<LifeOsProvider initialData={data}>{ui}</LifeOsProvider>);
}
