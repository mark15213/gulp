import Link from "next/link";
import { notFound } from "next/navigation";
import { getPack, getSnapshot } from "@gulp/api-client";
import { ReaderToggle } from "@/components/snapshot/ReaderToggle";
import { StartButton } from "@/components/snapshot/StartButton";
import { ExportActions } from "@/components/snapshot/ExportActions";
import { ProcessingPoller } from "@/components/snapshot/ProcessingPoller";
import styles from "@/components/snapshot/SnapshotStatusView.module.css";
import { safeHost } from "@/lib/pack";

export const dynamic = "force-dynamic";

export default async function SnapshotPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let snap;
  try {
    snap = await getSnapshot(id);
  } catch {
    notFound();
  }

  const source = safeHost(snap.origin_url);

  return (
    <div className={styles.page}>
      <Link href="/inbox" className={styles.back}>← Inbox</Link>
      <h1 className={`t-title-l ${styles.title}`}>{snap.title}</h1>
      <p className={`t-data ${styles.source}`}>{source}</p>

      {snap.status === "unprocessed" && (
        <div className={styles.actions}>
          <StartButton id={id} />
          <ExportActions id={id} status={snap.status} />
          {snap.origin_url && (
            <a className={styles.open} href={snap.origin_url} target="_blank" rel="noreferrer">Open original</a>
          )}
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
            <StartButton id={id} label="▶ Retry" />
            <ExportActions id={id} status={snap.status} />
            {snap.origin_url && (
              <a className={styles.open} href={snap.origin_url} target="_blank" rel="noreferrer">Open original</a>
            )}
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

      {snap.status === "ready" &&
        (await renderPack(id, snap.content_body, snap.cards_status ?? null))}
    </div>
  );
}

async function renderPack(
  id: string,
  original: string | null,
  cardsStatus: "generating" | "ready" | "failed" | null,
) {
  const pack = await getPack(id);
  if (!pack) {
    return <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>Pack not available.</p>;
  }
  return <ReaderToggle pack={pack} original={original} snapshotId={id} cardsStatus={cardsStatus} />;
}
