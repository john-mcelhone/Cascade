"use client";

import { Button } from "@/components/ui/button";

export default function ProjectError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 px-5 py-8 text-center">
      <h2 className="text-md font-medium">This project did not load.</h2>
      <p className="max-w-md text-sm text-text-muted">{error.message}</p>
      <Button onClick={() => reset()}>Try again</Button>
    </div>
  );
}
