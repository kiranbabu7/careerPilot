"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, Loader2 } from "lucide-react";

import { ApplicationBoard } from "@/components/applications/application-board";
import { ApplicationDetailPanel } from "@/components/applications/application-detail-panel";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { applicationsApi, type Application } from "@/lib/api";

export default function ApplicationsPage() {
  const [stageOrder, setStageOrder] = useState<string[]>([]);
  const [stages, setStages] = useState<Record<string, Application[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const loadBoard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await applicationsApi.list();
      setStageOrder(data.stage_order);
      setStages(data.stages);
    } catch {
      setError("Failed to load applications.");
      setStages({});
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBoard();
  }, [loadBoard]);

  const handleApplicationUpdated = (updated: Application) => {
    void loadBoard();
    setSelectedId(updated.id);
  };

  const totalCount = Object.values(stages).reduce(
    (sum, items) => sum + items.length,
    0,
  );

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="flex flex-col gap-6 p-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Applications</h1>
              <p className="text-sm text-muted-foreground">
                Track your pipeline from applied through offer.
              </p>
            </div>
            <Button asChild variant="outline" size="sm">
              <Link href="/opportunities">
                <Briefcase className="h-4 w-4" />
                Browse opportunities
              </Link>
            </Button>
          </div>

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading Kanban board...
            </div>
          ) : error ? (
            <Card>
              <CardContent className="flex items-center justify-between p-6">
                <p className="text-sm text-destructive">{error}</p>
                <Button size="sm" variant="outline" onClick={() => void loadBoard()}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          ) : totalCount === 0 ? (
            <Card className="max-w-xl">
              <CardContent className="space-y-3 p-6 text-sm text-muted-foreground">
                <p>No applications tracked yet.</p>
                <p>
                  Mark an opportunity as applied from the Opportunities page to create
                  your first application card.
                </p>
                <Button asChild size="sm">
                  <Link href="/opportunities">Go to opportunities</Link>
                </Button>
              </CardContent>
            </Card>
          ) : (
            <ApplicationBoard
              stageOrder={stageOrder}
              stages={stages}
              onSelect={setSelectedId}
            />
          )}
        </div>

        <ApplicationDetailPanel
          applicationId={selectedId}
          onClose={() => setSelectedId(null)}
          onUpdated={handleApplicationUpdated}
        />
      </AppShell>
    </ProtectedRoute>
  );
}
