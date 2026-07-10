import React from "react";
import { PageFrame } from "./PageFrame";
import styles from "./PageLoading.module.css";

type LoadingLayout = "dashboard" | "library" | "workspace";

export function PageLoading({ layout }: { layout: LoadingLayout }) {
  const variant =
    layout === "dashboard"
      ? "dashboard"
      : layout === "workspace"
        ? "workspace"
        : "content";

  return (
    <PageFrame variant={variant} className={styles.page}>
      <div className={styles.loading} aria-busy="true" aria-live="polite">
        <span className={styles.srOnly}>Loading page</span>
        <header className={styles.header} aria-hidden="true">
          <span className={`${styles.block} ${styles.title}`} />
          <span className={`${styles.block} ${styles.meta}`} />
        </header>
        {layout === "dashboard" ? <DashboardSkeleton /> : null}
        {layout === "library" ? <LibrarySkeleton /> : null}
        {layout === "workspace" ? <WorkspaceSkeleton /> : null}
      </div>
    </PageFrame>
  );
}

function DashboardSkeleton() {
  return (
    <>
      <div className={styles.dashboardOverview} aria-hidden="true">
        <span className={`${styles.block} ${styles.hero}`} />
        <span className={`${styles.block} ${styles.summary}`} />
      </div>
      <span className={`${styles.block} ${styles.label}`} aria-hidden="true" />
      <div className={styles.cardGrid} aria-hidden="true">
        {Array.from({ length: 3 }, (_, index) => (
          <span key={index} className={`${styles.block} ${styles.card}`} />
        ))}
      </div>
    </>
  );
}

function LibrarySkeleton() {
  return (
    <div className={styles.library} aria-hidden="true">
      <span className={`${styles.block} ${styles.filters}`} />
      <div className={styles.libraryGrid}>
        {Array.from({ length: 6 }, (_, index) => (
          <span
            key={index}
            className={`${styles.block} ${styles.libraryCard}`}
          />
        ))}
      </div>
    </div>
  );
}

function WorkspaceSkeleton() {
  return (
    <div className={styles.workspace} aria-hidden="true">
      <span className={`${styles.block} ${styles.pane}`} />
      <span className={`${styles.block} ${styles.pane}`} />
      <span className={`${styles.block} ${styles.reader}`} />
    </div>
  );
}
