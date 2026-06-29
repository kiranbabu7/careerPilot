"use client";

export function JsonViewer({ data }: { data: unknown }) {
  return (
    <pre className="max-h-80 overflow-auto rounded-lg border border-border bg-muted/30 p-3 text-xs leading-relaxed">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
