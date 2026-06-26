import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function InterviewsPage() {
  return (
    <AppShell>
      <div className="p-8">
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle>Interviews</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground">
            Interview prep plans arrive in Phase 7.
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
