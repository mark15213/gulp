// Static stand-in for the Today payload. No backend in this slice — when S0
// lands the API, this shape is what @gulp/api-client will return.

export type MasteryState = "new" | "learning" | "known" | "due" | "at-risk";
export type ObjectType = "snapshot" | "conversation" | "subscription";

export interface DigestItem {
  id: string;
  type: ObjectType;
  title: string;
  summary: string;
  source: string;
  time: string;
  cards: number;
  state: MasteryState;
  /** "why it's worth your time, how it connects" (docs/03 §7.11). */
  reason: string;
}

export interface RecentItem {
  id: string;
  type: ObjectType;
  title: string;
  source: string;
  time: string;
  status: "ready" | "processing" | "attention";
}

export interface TodayData {
  date: string;
  greeting: string;
  dueCount: number;
  dueConcepts: number;
  streak: number;
  newToConfirm: number;
  resume: { detail: string; progress: string };
  digest: DigestItem[];
  recent: RecentItem[];
}

export const today: TodayData = {
  date: "Tuesday, June 24",
  greeting: "Here's what's worth your 5 minutes.",
  dueCount: 5,
  dueConcepts: 3,
  streak: 5,
  newToConfirm: 3,
  resume: { detail: "Gulp session", progress: "4 / 12" },
  digest: [
    {
      id: "d1",
      type: "snapshot",
      title: "How spaced repetition actually works",
      summary:
        "The testing effect plus expanding intervals — why retrieval beats rereading, and where SM-2 breaks down.",
      source: "gwern.net",
      time: "2h ago",
      cards: 4,
      state: "new",
      reason: "Builds on your “memory consolidation” concept",
    },
    {
      id: "d2",
      type: "subscription",
      title: "The Batch — frontier models get cheaper to run",
      summary:
        "Weekly roundup: inference cost curves, a new open-weights release, and what it means for on-device.",
      source: "DeepLearning.AI",
      time: "5h ago",
      cards: 3,
      state: "due",
      reason: "Connects to 3 cards you're learning on inference",
    },
    {
      id: "d3",
      type: "conversation",
      title: "Why does FSRS beat SM-2 in practice?",
      summary:
        "Your chat on scheduling — you worked out where the half-life model diverges from fixed multipliers.",
      source: "Gulp chat",
      time: "Yesterday",
      cards: 2,
      state: "learning",
      reason: "2 candidate cards still waiting to be confirmed",
    },
  ],
  recent: [
    {
      id: "r1",
      type: "snapshot",
      title: "The Bitter Lesson",
      source: "incompleteideas.net · PDF",
      time: "12m ago",
      status: "ready",
    },
    {
      id: "r2",
      type: "subscription",
      title: "Import AI #402",
      source: "Forwarded · newsletter",
      time: "20m ago",
      status: "processing",
    },
    {
      id: "r3",
      type: "snapshot",
      title: "Screenshot — lecture slide",
      source: "Share sheet · image",
      time: "1h ago",
      status: "attention",
    },
  ],
};
