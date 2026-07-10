"use client";

import { createContext, useContext } from "react";

export type ChatAttachment = { id: string; label: string };

type ReaderChat = { addToChat: (a: ChatAttachment) => void };

export const ReaderChatCtx = createContext<ReaderChat | null>(null);

export function useReaderChat(): ReaderChat | null {
  return useContext(ReaderChatCtx);
}
