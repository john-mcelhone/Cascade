import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-5 text-center">
      <h1 className="text-lg font-medium">Nothing here.</h1>
      <p className="max-w-md text-sm text-text-muted">
        That URL doesn&apos;t point at anything in Cascade. If you got here from
        a link in our docs, please tell us — the contact link is at the bottom
        of every page.
      </p>
      <Link href="/projects">
        <Button>Go to the workspace</Button>
      </Link>
    </div>
  );
}
