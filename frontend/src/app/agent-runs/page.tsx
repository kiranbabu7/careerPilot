import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AgentRunsPage() {
  return (
    <AppShell>
      <div className="p-8">
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle>Agent Runs</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground">
            Inspectable agent execution history arrives in Phase 8.
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
