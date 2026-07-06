import React from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./IconButton.module.css";

// Low-emphasis square action (docs/03 §7.4). Ink line-art at rest; neutral
// actions warm to banana on hover (the token's "highlight / hover" role),
// destructive ones redden. Labels live in the tooltip + accessible name.
type Tone = "neutral" | "danger";

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  tone?: Tone;
  active?: boolean;
  children: ReactNode;
}

export function IconButton({
  label,
  tone = "neutral",
  active = false,
  className,
  children,
  ...props
}: IconButtonProps) {
  return (
    <button
      type="button"
      className={`${styles.btn} ${styles[tone]} ${active ? styles.active : ""} ${className ?? ""}`}
      aria-label={label}
      title={label}
      {...props}
    >
      {children}
    </button>
  );
}
