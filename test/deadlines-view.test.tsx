import { screen } from "@testing-library/react";

import { DeadlinesView } from "@/components/life-os/deadlines-view";
import { renderWithLifeOs } from "@/test/test-utils";

describe("DeadlinesView", () => {
  it("renders the chosen deadline bucket", () => {
    renderWithLifeOs(<DeadlinesView initialQueryString="bucket=overdue" />);

    expect(screen.getAllByText("Overdue").length).toBeGreaterThan(0);
    expect(screen.getByText("Property tax installment")).toBeInTheDocument();
    expect(screen.queryByText("Submit lease renewal packet")).not.toBeInTheDocument();
  });
});
