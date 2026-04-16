import { render } from "@testing-library/react";

import { buildSeedLifeItems } from "@/lib/life-os/mock-data";
import { LifeOsProvider } from "@/lib/life-os/state";
import type { LifeItem } from "@/lib/life-os/types";

const REFERENCE_DATE = new Date("2026-04-16T09:00:00-05:00");

export function renderWithLifeOs(
  ui: React.ReactElement,
  { items = buildSeedLifeItems(REFERENCE_DATE) }: { items?: LifeItem[] } = {},
) {
  return render(<LifeOsProvider initialItems={items}>{ui}</LifeOsProvider>);
}

export { REFERENCE_DATE };
