import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { Metadata } from "next";
import {
  CHAPTERS,
  getChapter,
  getChapterNeighbors,
} from "@/lib/learn/chapters";
import {
  Chapter,
  Lead,
  NextChapter,
  ReadingToc,
} from "@/components/learn/content";

export function generateStaticParams() {
  return CHAPTERS.map((c) => ({ chapter: c.slug }));
}

interface ChapterRouteParams {
  params: Promise<{ chapter: string }>;
}

export async function generateMetadata({
  params,
}: ChapterRouteParams): Promise<Metadata> {
  const { chapter } = await params;
  const meta = getChapter(chapter);
  if (!meta) return { title: "Chapter not found" };
  return {
    title: `${meta.number}. ${meta.title}`,
    description: meta.subtitle,
  };
}

/**
 * Dynamic chapter route. The content for each chapter lives at
 * `src/content/learn/{slug}.tsx` as a default-export React component;
 * the two content agents own that directory. If a chapter file doesn't
 * exist yet, we render a "Coming soon" placeholder so the route still
 * works during parallel authoring.
 */
export default async function ChapterPage({ params }: ChapterRouteParams) {
  const { chapter } = await params;
  const meta = getChapter(chapter);
  if (!meta) return notFound();

  const neighbors = getChapterNeighbors(chapter);

  const Content = await loadChapterContent(chapter);

  return (
    <div className="relative flex w-full">
      <div className="flex-1 min-w-0">
        <Suspense fallback={<ChapterSkeleton slug={chapter} />}>
          {Content ? (
            <Content />
          ) : (
            <Chapter
              slug={meta.slug}
              number={meta.number}
              title={meta.title}
              subtitle={meta.subtitle}
              difficulty={meta.difficulty}
              readMinutes={meta.readMinutes}
              authorNote="Coming soon. The content for this chapter is being written. The widgets and routing are ready."
            >
              <Lead>
                This chapter is a placeholder. Content lands in
                {" "}
                <code className="rounded-sm bg-surface-subtle px-1 font-mono text-sm">
                  src/content/learn/{meta.slug}.tsx
                </code>
                {" "}as it&apos;s authored. Until then, the route works and the
                sidebar progress tracker can still be exercised.
              </Lead>
              <NextChapter
                prevHref={neighbors.prev ? `/learn/${neighbors.prev.slug}` : undefined}
                prevTitle={neighbors.prev?.title}
                nextHref={neighbors.next ? `/learn/${neighbors.next.slug}` : undefined}
                nextTitle={neighbors.next?.title}
              />
            </Chapter>
          )}
        </Suspense>
      </div>
      <ReadingToc />
    </div>
  );
}

function ChapterSkeleton({ slug }: { slug: string }) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-12 animate-pulse">
      <div className="h-3 w-32 rounded-sm bg-surface-subtle" />
      <div className="h-6 w-3/4 rounded-sm bg-surface-subtle" />
      <div className="h-4 w-1/2 rounded-sm bg-surface-subtle" />
      <div className="mt-4 flex flex-col gap-2">
        <div className="h-4 w-full rounded-sm bg-surface-subtle" />
        <div className="h-4 w-11/12 rounded-sm bg-surface-subtle" />
        <div className="h-4 w-10/12 rounded-sm bg-surface-subtle" />
      </div>
      <span className="sr-only">Loading chapter {slug}</span>
    </div>
  );
}

/**
 * Dynamically import the chapter content module if it exists. We catch
 * errors (specifically MODULE_NOT_FOUND) so that the placeholder renders
 * while the content agents are still writing.
 */
async function loadChapterContent(
  slug: string,
): Promise<React.ComponentType | null> {
  try {
    // Use a webpackInclude-style dynamic import so Next bundles every
    // chapter file that exists at build time.
    const mod = await import(`@/content/learn/${slug}`);
    if (mod?.default) return mod.default as React.ComponentType;
    return null;
  } catch {
    return null;
  }
}
