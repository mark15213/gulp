import { getLibrary } from "@/lib/serverApi";
import { LibraryList } from "@/components/library/LibraryList";
import { PageFrame, PageHeader } from "@/components/shell/PageFrame";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

// Library — the shelf: everything digested (`ready`), filterable by tag.
export default async function LibraryPage() {
  const { items, count } = await getLibrary();
  return (
    <PageFrame className={styles.page}>
      <PageHeader
        title="Library"
        description={<span className="t-data">{count} ready</span>}
      />
      <LibraryList items={items} />
    </PageFrame>
  );
}
