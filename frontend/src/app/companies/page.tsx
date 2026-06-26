import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function CompaniesPage() {
  return (
    <AppShell>
      <div className="p-8">
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle>Companies</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground">
            Company research and intelligence arrive in Phase 5.
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
