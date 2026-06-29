"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight, LayoutDashboard, Loader2, RefreshCw, Sparkles } from "lucide-react";

import { DecisionCard } from "@/components/agents/decision-card";
import { DecisionRecommendationContent } from "@/components/agents/decision-recommendation-content";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ApiError,
  decisionsApi,
  type DecisionRecommendation,
} from "@/lib/api";

const PAGE_SIZE = 12;

function DecisionsPageFallback() {
  return (
    <ProtectedRoute>
      <AppShell>
        <div className="flex flex-col gap-8 p-8">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Decisions</h1>
            <p className="text-sm text-muted-foreground">
              AI recommendations for your next career actions.
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading decisions...
          </div>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}

function DecisionsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const workflowIdFromUrl = searchParams.get("workflow_id");
  const selectedFromUrl = searchParams.get("selected");

  const [recommendations, setRecommendations] = useState<DecisionRecommendation[]>([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(selectedFromUrl);
  const [selectedDetail, setSelectedDetail] = useState<DecisionRecommendation | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await decisionsApi.list({
        workflow_id: workflowIdFromUrl ?? undefined,
        offset,
        limit: PAGE_SIZE,
      });
      setRecommendations(data.results);
      setCount(data.count);
    } catch (err) {
      setRecommendations([]);
      setCount(0);
      setError(err instanceof ApiError ? err.message : "Failed to load decisions");
    } finally {
      setLoading(false);
    }
  }, [offset, workflowIdFromUrl]);

  const loadDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const detail = await decisionsApi.detail(id);
      setSelectedDetail(detail);
    } catch (err) {
      setSelectedDetail(null);
      setDetailError(err instanceof ApiError ? err.message : "Failed to load decision detail");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (selectedFromUrl) {
      setSelectedId(selectedFromUrl);
    }
  }, [selectedFromUrl]);

  useEffect(() => {
    if (!selectedId) {
      setSelectedDetail(null);
      return;
    }
    void loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  const handleSelect = (id: string) => {
    setSelectedId(id);
    const params = new URLSearchParams(searchParams.toString());
    params.set("selected", id);
    router.replace(`/decisions?${params.toString()}`);
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await decisionsApi.generate(
        workflowIdFromUrl ? { workflow_id: workflowIdFromUrl } : undefined,
      );
      setSelectedId(result.recommendation.id);
      setSelectedDetail(result.recommendation);
      const params = new URLSearchParams(searchParams.toString());
      params.set("selected", result.recommendation.id);
      router.replace(`/decisions?${params.toString()}`);
      if (offset === 0) {
        await loadList();
      } else {
        setOffset(0);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate recommendation");
    } finally {
      setGenerating(false);
    }
  };

  const pageInfo = {
    start: count === 0 ? 0 : offset + 1,
    end: Math.min(offset + PAGE_SIZE, count),
  };

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="flex flex-col gap-8 p-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Decisions</h1>
              <p className="text-sm text-muted-foreground">
                Prioritized next actions across opportunities, applications, materials, and
                interview prep.
              </p>
              {workflowIdFromUrl ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  Scoped to workspace{" "}
                  <span className="font-mono text-foreground/80">{workflowIdFromUrl}</span>
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" disabled={generating} onClick={() => void handleGenerate()}>
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Generate recommendation
                  </>
                )}
              </Button>
              {workflowIdFromUrl ? (
                <Button asChild variant="outline" size="sm">
                  <Link href="/decisions">
                    <RefreshCw className="h-4 w-4" />
                    Clear scope
                  </Link>
                </Button>
              ) : null}
              <Button asChild variant="outline" size="sm">
                <Link href="/workspace">
                  <LayoutDashboard className="h-4 w-4" />
                  Workspace
                </Link>
              </Button>
            </div>
          </div>

          {selectedId ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Selected recommendation</CardTitle>
              </CardHeader>
              <CardContent>
                {detailLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading recommendation...
                  </div>
                ) : detailError ? (
                  <p className="text-sm text-destructive">{detailError}</p>
                ) : selectedDetail ? (
                  <DecisionRecommendationContent recommendation={selectedDetail} />
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading past recommendations...
            </div>
          ) : error ? (
            <Card>
              <CardContent className="flex items-center justify-between p-6">
                <p className="text-sm text-destructive">{error}</p>
                <Button size="sm" variant="outline" onClick={() => void loadList()}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          ) : recommendations.length === 0 ? (
            <Card className="max-w-xl">
              <CardContent className="space-y-3 p-6 text-sm text-muted-foreground">
                <p>No decision recommendations yet.</p>
                <p>
                  Generate one to get a prioritized list of what to do next across your
                  career pipeline.
                </p>
                <Button size="sm" disabled={generating} onClick={() => void handleGenerate()}>
                  <Sparkles className="h-4 w-4" />
                  Generate recommendation
                </Button>
              </CardContent>
            </Card>
          ) : (
            <section className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">Past recommendations</h2>
                <p className="text-xs text-muted-foreground">
                  {pageInfo.start}-{pageInfo.end} of {count}
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {recommendations.map((recommendation) => (
                  <DecisionCard
                    key={recommendation.id}
                    recommendation={recommendation}
                    selected={selectedId === recommendation.id}
                    onSelect={handleSelect}
                  />
                ))}
              </div>
              {count > PAGE_SIZE ? (
                <div className="flex items-center justify-between pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset === 0}
                    onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset + PAGE_SIZE >= count}
                    onClick={() => setOffset((value) => value + PAGE_SIZE)}
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              ) : null}
            </section>
          )}
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}

export default function DecisionsPage() {
  return (
    <Suspense fallback={<DecisionsPageFallback />}>
      <DecisionsPageContent />
    </Suspense>
  );
}
