"use client";

import React, { useEffect, useState, type ReactNode } from "react";
import { ReaderChatCtx, type ChatAttachment } from "./ReaderChatContext";
import { ReaderTopBar } from "./ReaderTopBar";
import { ChatPanel } from "./ChatPanel";
import type { GenreSelect } from "./GenreSelect";
import styles from "./ReaderLayout.module.css";

export function ReaderLayout({
  sidebar,
  snapshotId,
  title,
  genre,
  originUrl,
  packReady,
  children,
}: {
  sidebar: ReactNode;
  snapshotId: string;
  title: string;
  genre: React.ComponentProps<typeof GenreSelect>["genre"];
  originUrl: string | null;
  packReady: boolean;
  children: ReactNode;
}) {
  const [navOpen, setNavOpen] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);

  useEffect(() => {
    setNavOpen(localStorage.getItem("reader:navOpen") !== "false");
  }, []);
  useEffect(() => {
    localStorage.setItem("reader:navOpen", String(navOpen));
  }, [navOpen]);

  function addToChat(a: ChatAttachment) {
    setAttachments((xs) => (xs.some((x) => x.id === a.id) ? xs : [...xs, a]));
    setChatOpen(true);
  }
  function removeAttachment(id: string) {
    setAttachments((xs) => xs.filter((x) => x.id !== id));
  }

  const chatShown = packReady && chatOpen;

  return (
    <ReaderChatCtx.Provider value={{ addToChat }}>
      <div
        className={styles.layout}
        data-nav={navOpen ? "open" : "closed"}
        data-chat={chatShown ? "open" : "closed"}
      >
        {navOpen && <div className={styles.nav}>{sidebar}</div>}
        <div className={styles.center}>
          <ReaderTopBar
            title={title}
            genre={genre}
            snapshotId={snapshotId}
            originUrl={originUrl}
            navOpen={navOpen}
            onToggleNav={() => setNavOpen((v) => !v)}
            chatEnabled={packReady}
            chatOpen={chatOpen}
            onToggleChat={() => setChatOpen((v) => !v)}
          />
          <div className={styles.reading}>{children}</div>
        </div>
        {chatShown && (
          <div className={styles.chat}>
            <ChatPanel
              snapshotId={snapshotId}
              attachments={attachments}
              onRemoveAttachment={removeAttachment}
              onClose={() => setChatOpen(false)}
            />
          </div>
        )}
      </div>
    </ReaderChatCtx.Provider>
  );
}
