import { notFound } from "next/navigation";
import { getPack, getSnapshot } from "@/lib/serverApi";
import { Sidebar } from "@/components/shell/Sidebar";
import { ReaderLayout } from "@/components/snapshot/ReaderLayout";
import { ReaderToggle } from "@/components/snapshot/ReaderToggle";
import { StartButton } from "@/components/snapshot/StartButton";
import { ExportActions } from "@/components/snapshot/ExportActions";
import { ProcessingPoller } from "@/components/snapshot/ProcessingPoller";
import styles from "@/components/snapshot/SnapshotStatusView.module.css";

export const dynamic = "force-dynamic";

export default async function SnapshotPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let snap;
  try {
    snap = await getSnapshot(id);
  } catch {
    notFound();
  }

  const body = (
    <>
      {snap.status === "unprocessed" && (
        <div className={styles.actions}>
          <StartButton id={id} />
          <ExportActions id={id} status={snap.status} />
        </div>
      )}

      {(snap.status === "processing" || snap.status === "queued") && (
        <>
          <ProcessingPoller id={id} />
          <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>Reading it for you…</p>
          <div className={styles.skeleton} />
          <div className={styles.skeleton} />
          <div className={`${styles.skeleton} ${styles.short}`} />
        </>
      )}

      {snap.status === "needs_attention" && (
        <>
          <div className={styles.banner}>Couldn&apos;t fully read this.</div>
          <div className={styles.actions}>
            <StartButton id={id} label="Retry" />
            <ExportActions id={id} status={snap.status} />
          </div>
        </>
      )}

      {snap.status === "exported" && (
        <div className={styles.actions}>
          <ExportActions id={id} status={snap.status} />
          <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>
            Exported — run it in Claude Code, then upload the result zip.
          </p>
        </div>
      )}

      {snap.status === "ready" && (await renderPack(id, snap.cards_status ?? null))}
    </>
  );

  return (
    <ReaderLayout
      sidebar={<Sidebar />}
      snapshotId={id}
      title={snap.title}
      genre={snap.genre ?? null}
      originUrl={snap.origin_url}
      packReady={snap.status === "ready"}
    >
      {body}
    </ReaderLayout>
  );
}

async function renderPack(
  id: string,
  cardsStatus: "generating" | "ready" | "failed" | null,
) {
  const pack = await getPack(id);
  if (!pack) {
    return <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>Pack not available.</p>;
  }
  return <ReaderToggle pack={pack} snapshotId={id} cardsStatus={cardsStatus} />;
}
