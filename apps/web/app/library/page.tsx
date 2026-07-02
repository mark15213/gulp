import { getLibrary } from "@gulp/api-client";
import { LibraryList } from "@/components/library/LibraryList";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

// Library — the shelf: everything digested (`ready`), filterable by tag.
export default async function LibraryPage() {
  const { items, count } = await getLibrary();
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className="t-title-l">Library</h1>
        <span className={`t-data ${styles.count}`}>{count}</span>
      </header>
      <LibraryList items={items} />
    </div>
  );
}
