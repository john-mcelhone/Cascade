/**
 * Canonical chapter manifest for the /learn tutorial. The content agents
 * import this list to keep slug + title + ordering in sync with routing,
 * sidebar, and footer navigation.
 *
 * Reading times and difficulty levels mirror the curriculum plan.
 */

export type Difficulty = "Beginner" | "Intermediate" | "Advanced";

export interface ChapterMeta {
  /** URL slug. */
  slug: string;
  /** Display number (1–10). */
  number: number;
  /** Display title. */
  title: string;
  /** One-line subtitle shown under the hero. */
  subtitle: string;
  /** Estimated reading time, in whole minutes. */
  readMinutes: number;
  /** Reading-difficulty chip. */
  difficulty: Difficulty;
}

export const CHAPTERS: ChapterMeta[] = [
  {
    slug: "1-what-is-a-turbine",
    number: 1,
    title: "What is a turbine?",
    subtitle: "A turbine extracts work from a flowing fluid.",
    readMinutes: 5,
    difficulty: "Beginner",
  },
  {
    slug: "2-brayton-cycle",
    number: 2,
    title: "The Brayton cycle",
    subtitle: "Compress, heat, expand. The leftover is net power.",
    readMinutes: 7,
    difficulty: "Beginner",
  },
  {
    slug: "3-why-its-hard",
    number: 3,
    title: "Why turbines are hard",
    subtitle: "Velocity triangles, conservation laws, and the Euler equation.",
    readMinutes: 9,
    difficulty: "Intermediate",
  },
  {
    slug: "4-radial-vs-axial",
    number: 4,
    title: "Radial vs axial",
    subtitle: "Specific speed sets the geometry family.",
    readMinutes: 8,
    difficulty: "Intermediate",
  },
  {
    slug: "5-loss-models",
    number: 5,
    title: "Loss models",
    subtitle: "Where the missing efficiency goes, and how we account for it.",
    readMinutes: 11,
    difficulty: "Intermediate",
  },
  {
    slug: "6-design-exploration",
    number: 6,
    title: "Design exploration",
    subtitle: "Generate two thousand candidates and let the Pareto front emerge.",
    readMinutes: 9,
    difficulty: "Intermediate",
  },
  {
    slug: "7-performance-maps",
    number: 7,
    title: "Performance maps",
    subtitle: "Surge, choke, and the banana-shaped region in between.",
    readMinutes: 10,
    difficulty: "Intermediate",
  },
  {
    slug: "8-rotor-dynamics",
    number: 8,
    title: "Rotor dynamics",
    subtitle: "Critical speeds, mode shapes, and the Campbell diagram.",
    readMinutes: 12,
    difficulty: "Advanced",
  },
  {
    slug: "9-the-workflow",
    number: 9,
    title: "A complete workflow",
    subtitle: "From cycle sketch to STEP export, in one afternoon.",
    readMinutes: 12,
    difficulty: "Advanced",
  },
  {
    slug: "10-validation",
    number: 10,
    title: "Validation: trust but verify",
    subtitle: "Every solver lies. Here's how to tell which ones lie less.",
    readMinutes: 8,
    difficulty: "Advanced",
  },
];

/** Find chapter metadata by slug, or null if not a known chapter. */
export function getChapter(slug: string): ChapterMeta | null {
  return CHAPTERS.find((c) => c.slug === slug) ?? null;
}

/** Neighboring chapter slugs (previous, next) for footer nav. */
export function getChapterNeighbors(slug: string): {
  prev: ChapterMeta | null;
  next: ChapterMeta | null;
} {
  const idx = CHAPTERS.findIndex((c) => c.slug === slug);
  if (idx === -1) return { prev: null, next: null };
  return {
    prev: idx > 0 ? CHAPTERS[idx - 1] : null,
    next: idx < CHAPTERS.length - 1 ? CHAPTERS[idx + 1] : null,
  };
}

export const LEARN_PROGRESS_KEY = "cascade.learn.progress";
export const LEARN_LAST_VISITED_KEY = "cascade.learn.lastVisited";
