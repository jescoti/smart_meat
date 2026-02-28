/**
 * Tests for the SearchFilters component.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SearchFilters } from "./SearchFilters";
import type { SearchFilterValues } from "./SearchFilters";

const defaultFilters: SearchFilterValues = {
  groupId: "",
  sender: "",
  dateFrom: "",
  dateTo: "",
};

describe("SearchFilters", () => {
  it("renders a sender input", () => {
    render(
      <SearchFilters filters={defaultFilters} onChange={vi.fn()} />,
    );

    expect(screen.getByLabelText(/sender/i)).toBeInTheDocument();
  });

  it("renders date from input", () => {
    render(
      <SearchFilters filters={defaultFilters} onChange={vi.fn()} />,
    );

    expect(screen.getByLabelText(/from/i)).toBeInTheDocument();
  });

  it("renders date to input", () => {
    render(
      <SearchFilters filters={defaultFilters} onChange={vi.fn()} />,
    );

    expect(screen.getByLabelText(/to/i)).toBeInTheDocument();
  });

  it("renders group id input", () => {
    render(
      <SearchFilters filters={defaultFilters} onChange={vi.fn()} />,
    );

    expect(screen.getByLabelText(/group/i)).toBeInTheDocument();
  });

  it("displays current filter values", () => {
    const filters: SearchFilterValues = {
      groupId: "group-123",
      sender: "alice@example.com",
      dateFrom: "2024-01-01",
      dateTo: "2024-12-31",
    };

    render(<SearchFilters filters={filters} onChange={vi.fn()} />);

    expect(screen.getByLabelText(/sender/i)).toHaveValue("alice@example.com");
    expect(screen.getByLabelText(/from/i)).toHaveValue("2024-01-01");
    expect(screen.getByLabelText(/to/i)).toHaveValue("2024-12-31");
    expect(screen.getByLabelText(/group/i)).toHaveValue("group-123");
  });

  it("calls onChange when sender changes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SearchFilters filters={defaultFilters} onChange={onChange} />,
    );

    const input = screen.getByLabelText(/sender/i);
    await user.type(input, "bob");

    expect(onChange).toHaveBeenCalled();
  });

  it("calls onChange when date from changes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SearchFilters filters={defaultFilters} onChange={onChange} />,
    );

    const input = screen.getByLabelText(/from/i);
    await user.type(input, "2024-01-01");

    expect(onChange).toHaveBeenCalled();
  });

  it("calls onChange when date to changes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SearchFilters filters={defaultFilters} onChange={onChange} />,
    );

    const input = screen.getByLabelText(/to/i);
    await user.type(input, "2024-12-31");

    expect(onChange).toHaveBeenCalled();
  });

  it("calls onChange when group changes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SearchFilters filters={defaultFilters} onChange={onChange} />,
    );

    const input = screen.getByLabelText(/group/i);
    await user.type(input, "group-1");

    expect(onChange).toHaveBeenCalled();
  });
});
