/**
 * Tests for the SearchBar component.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SearchBar } from "./SearchBar";

describe("SearchBar", () => {
  it("renders a search input", () => {
    render(<SearchBar value="" onChange={vi.fn()} onSubmit={vi.fn()} />);

    expect(
      screen.getByPlaceholderText(/search/i),
    ).toBeInTheDocument();
  });

  it("renders a submit button", () => {
    render(<SearchBar value="" onChange={vi.fn()} onSubmit={vi.fn()} />);

    expect(
      screen.getByRole("button", { name: /search/i }),
    ).toBeInTheDocument();
  });

  it("displays the current value", () => {
    render(
      <SearchBar value="meeting notes" onChange={vi.fn()} onSubmit={vi.fn()} />,
    );

    const input = screen.getByPlaceholderText(/search/i);
    expect(input).toHaveValue("meeting notes");
  });

  it("calls onChange when typing", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SearchBar value="" onChange={onChange} onSubmit={vi.fn()} />);

    const input = screen.getByPlaceholderText(/search/i);
    await user.type(input, "test");

    expect(onChange).toHaveBeenCalled();
  });

  it("calls onSubmit when form is submitted", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<SearchBar value="test" onChange={vi.fn()} onSubmit={onSubmit} />);

    const button = screen.getByRole("button", { name: /search/i });
    await user.click(button);

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("calls onSubmit when pressing Enter", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<SearchBar value="test" onChange={vi.fn()} onSubmit={onSubmit} />);

    const input = screen.getByPlaceholderText(/search/i);
    await user.type(input, "{Enter}");

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
