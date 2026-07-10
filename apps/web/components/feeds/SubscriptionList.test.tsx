import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { Subscription } from "@gulp/api-client";
import { SubscriptionList } from "./SubscriptionList";

afterEach(() => cleanup());

const sub = (over: Partial<Subscription>): Subscription =>
  ({
    id: "s1",
    title: "Anthropic Research",
    feed_url: "rsshub://anthropic/research",
    health: "active",
    muted: false,
    unread_count: 3,
    last_fetch_at: null,
    last_fetch_error: null,
    created_at: "2026-07-09T00:00:00Z",
    ...over,
  }) as Subscription;

const noop = () => {};

describe("SubscriptionList", () => {
  it("renders unread count and fires selection", () => {
    const onSelect = vi.fn();
    render(
      <SubscriptionList
        subscriptions={[sub({})]}
        selectedId={null}
        onSelect={onSelect}
        onToggleMute={noop}
        onDelete={noop}
        onAdd={noop}
      />,
    );
    expect(screen.getByText("3")).toBeDefined();
    expect(
      screen
        .getByRole("button", { name: "All feeds" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    fireEvent.click(screen.getByText("Anthropic Research"));
    expect(onSelect).toHaveBeenCalledWith("s1");
  });

  it("marks error health with the fetch error as tooltip", () => {
    render(
      <SubscriptionList
        subscriptions={[sub({ health: "error", last_fetch_error: "boom" })]}
        selectedId={null}
        onSelect={noop}
        onToggleMute={noop}
        onDelete={noop}
        onAdd={noop}
      />,
    );
    expect(screen.getByTitle("boom")).toBeDefined();
    expect(screen.getByText("Error")).toBeDefined();
    expect(screen.getByText(/Feed status: error, boom/)).toBeDefined();
    expect(
      screen.getByRole("button", { name: "Mute Anthropic Research" }),
    ).toBeDefined();
    expect(
      screen.getByRole("button", {
        name: "Unsubscribe from Anthropic Research",
      }),
    ).toBeDefined();
  });

  it("shows the empty state without feeds", () => {
    render(
      <SubscriptionList
        subscriptions={[]}
        selectedId={null}
        onSelect={noop}
        onToggleMute={noop}
        onDelete={noop}
        onAdd={noop}
      />,
    );
    expect(screen.getByText(/No feeds yet/)).toBeDefined();
  });
});
