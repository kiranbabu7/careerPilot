"use client";

import { useCallback, useEffect, useState } from "react";
import { Briefcase, Loader2, Search } from "lucide-react";
import Link from "next/link";

import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { opportunitiesApi, type Opportunity } from "@/lib/api";

export default function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOpportunities = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await opportunitiesApi.list();
      setOpportunities(data);
    } catch {
      setError("Failed to load opportunities.");
      setOpportunities([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOpportunities();
  }, [loadOpportunities]);

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="p-8">
          <div className="mb-8 space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">Opportunities</h1>
            <p className="text-sm text-muted-foreground">
              Jobs discovered by CareerPilot from Apify job boards, enriched with Tavily
              company research.
            </p>
          </div>

          {loading ? (
            <Card className="max-w-lg">
              <CardContent className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading discovered opportunities...
              </CardContent>
            </Card>
          ) : error ? (
            <Card className="max-w-lg border-destructive/30">
              <CardContent className="p-6 text-sm text-destructive">{error}</CardContent>
            </Card>
          ) : opportunities.length === 0 ? (
            <Card className="max-w-2xl">
              <CardContent className="space-y-4 p-8 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-muted">
                  <Search className="h-6 w-6 text-muted-foreground" />
                </div>
                <div className="space-y-2">
                  <p className="font-medium">No opportunities yet</p>
                  <p className="text-sm text-muted-foreground">
                    Start a career goal from Home to run the Planner and Job Search agents.
                    Apify will scan configured job boards; results appear here automatically.
                  </p>
                </div>
                <Button asChild variant="outline">
                  <Link href="/">Start a career goal</Link>
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {opportunities.map((opportunity) => (
                <OpportunityCard key={opportunity.id} opportunity={opportunity} />
              ))}
            </div>
          )}

          {!loading && opportunities.length > 0 ? (
            <p className="mt-6 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Briefcase className="h-3.5 w-3.5" />
              {opportunities.length} opportunit{opportunities.length === 1 ? "y" : "ies"}{" "}
              discovered
            </p>
          ) : null}
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
