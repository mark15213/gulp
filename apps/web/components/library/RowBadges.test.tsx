import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { RowBadges } from "./RowBadges";

afterEach(cleanup);

describe("RowBadges", () => {
  it("renders a media_type label", () => {
    render(<RowBadges mediaType="video" cardsStatus={null} />);
    expect(screen.getByText("Video")).toBeTruthy();
  });

  it("omits the media_type badge when null", () => {
    render(<RowBadges mediaType={null} cardsStatus="ready" />);
    expect(screen.queryByText("Article")).toBeNull();
    expect(screen.queryByText("PDF")).toBeNull();
  });

  it("shows cards generating and failed states", () => {
    const { rerender } = render(<RowBadges mediaType={null} cardsStatus="generating" />);
    expect(screen.getByText("Cards…")).toBeTruthy();
    rerender(<RowBadges mediaType={null} cardsStatus="failed" />);
    expect(screen.getByText("⚠ Cards")).toBeTruthy();
  });

  it("shows a subtle ready badge, and nothing when cards_status is null", () => {
    const { rerender } = render(<RowBadges mediaType={null} cardsStatus="ready" />);
    expect(screen.getByText("✓ Cards")).toBeTruthy();
    rerender(<RowBadges mediaType={null} cardsStatus={null} />);
    expect(screen.queryByText("✓ Cards")).toBeNull();
  });

  it("renders nothing when both are absent", () => {
    const { container } = render(<RowBadges mediaType={null} cardsStatus={null} />);
    expect(container.firstChild).toBeNull();
  });
});
