import React from "react";
import type { ReactNode } from "react";
import styles from "./PageFrame.module.css";

export function PageFrame({
  children,
  className,
  variant = "content",
}: {
  children: ReactNode;
  className?: string;
  variant?: "dashboard" | "content" | "workspace";
}) {
  return (
    <div
      className={[styles.frame, styles[variant], className]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  meta,
}: {
  title: string;
  description?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className={styles.header}>
      <div className={styles.heading}>
        <h1 className="t-title-l">{title}</h1>
        {description ? (
          <p className={styles.description}>{description}</p>
        ) : null}
      </div>
      {meta ? <div className={`t-data ${styles.meta}`}>{meta}</div> : null}
    </header>
  );
}
