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
        <>
          {/* Both routes are icon buttons whose names live in a tooltip, which
              left this state reading as an empty page. Name them in the body. */}
          <p className={styles.lede}>Not read yet. Two ways to get a pack:</p>
          <div className={styles.actions}>
            <StartButton id={id} />
            <span className={`t-data ${styles.hint}`}>Read it here, with your own model.</span>
          </div>
          <div className={styles.actions}>
            <ExportActions id={id} status={snap.status} />
            <span className={`t-data ${styles.hint}`}>
              Hand it to your agent — then run <code>/gulp-work</code> in Claude Code.
            </span>
          </div>
        </>
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
            <span className={`t-data ${styles.hint}`}>Retry here, or hand it to your agent.</span>
          </div>
        </>
      )}

      {snap.status === "exported" && (
        <>
          <p className={styles.lede}>
            Queued for your agent. Run <code>/gulp-work</code> in Claude Code — it submits
            the result back over MCP.
          </p>
          <div className={styles.actions}>
            <ExportActions id={id} status={snap.status} />
            <span className={`t-data ${styles.hint}`}>
              Or do it by hand: download the job, upload the result zip.
            </span>
          </div>
        </>
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
