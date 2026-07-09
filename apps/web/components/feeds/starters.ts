// Spec 2026-07-09 §7 — verified zero-config starter sources. Doubles as the
// test-source set: both address forms × genres × zh/en × high/low volume.
export type StarterSource = { feedUrl: string; title: string; note: string };

export const STARTER_SOURCES: StarterSource[] = [
  {
    feedUrl: "rsshub://anthropic/research",
    title: "Anthropic Research",
    note: "English AI research articles",
  },
  { feedUrl: "rsshub://sspai/index", title: "少数派", note: "Chinese long-form, high volume" },
  { feedUrl: "rsshub://qbitai/category/资讯", title: "量子位", note: "Chinese AI news" },
  { feedUrl: "rsshub://solidot/www", title: "Solidot", note: "Short tech news items" },
  { feedUrl: "rsshub://36kr/hot-list", title: "36氪热榜", note: "Ranked tech list" },
  {
    feedUrl: "rsshub://hellogithub/volume",
    title: "HelloGitHub 月刊",
    note: "Monthly open-source digest",
  },
  { feedUrl: "rsshub://v2ex/topics/hot", title: "V2EX 最热", note: "Forum threads" },
  { feedUrl: "rsshub://readhub/daily", title: "Readhub 每日早报", note: "One brief per day" },
  {
    feedUrl: "https://www.ruanyifeng.com/blog/atom.xml",
    title: "阮一峰的网络日志",
    note: "Weekly, plain Atom",
  },
  {
    feedUrl: "https://rss.arxiv.org/rss/cs.AI",
    title: "arXiv cs.AI",
    note: "Papers — exercises the paper pipeline",
  },
  {
    feedUrl: "https://simonwillison.net/atom/everything/",
    title: "Simon Willison",
    note: "English AI blog, plain Atom",
  },
  { feedUrl: "https://hnrss.org/best", title: "Hacker News Best", note: "Link aggregation" },
];
