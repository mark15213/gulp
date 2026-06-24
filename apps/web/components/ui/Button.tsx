import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Button.module.css";

// Buttons (docs/03 §7.4). One primary per screen — blue means "act" (§1.2.2).
type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  iconRight?: ReactNode;
  iconLeft?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  iconRight,
  iconLeft,
  children,
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`${styles.btn} ${styles[variant]} ${styles[size]} ${className ?? ""}`}
      {...props}
    >
      {iconLeft}
      {children}
      {iconRight}
    </button>
  );
}
