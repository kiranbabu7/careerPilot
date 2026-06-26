import { Separator } from "@/components/ui/separator";

export function AuthDivider() {
  return (
    <div className="relative my-6">
      <Separator />
      <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-2 text-xs text-muted-foreground">
        or
      </span>
    </div>
  );
}
