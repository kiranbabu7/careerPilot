"use client";

import { useCallback, useEffect, useState } from "react";
import { Building2, Loader2 } from "lucide-react";
import Link from "next/link";

import { CompanyCard } from "@/components/companies/company-card";
import { CompanyDetailSheet } from "@/components/companies/company-detail-sheet";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { companyHasOpportunities } from "@/components/companies/company-utils";
import { companiesApi, type CompanySummary } from "@/lib/api";

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<CompanySummary | null>(null);

  const loadCompanies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await companiesApi.list();
      setCompanies(data.filter(companyHasOpportunities));
    } catch {
      setError("Failed to load companies.");
      setCompanies([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCompanies();
  }, [loadCompanies]);

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="p-8">
          <div className="mb-8 space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">Companies</h1>
            <p className="text-sm text-muted-foreground">
              Company intelligence aggregated from your discovered opportunities and
              on-demand Tavily research.
            </p>
          </div>

          {loading ? (
            <Card className="max-w-lg">
              <CardContent className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading companies...
              </CardContent>
            </Card>
          ) : error ? (
            <Card className="max-w-lg border-destructive/30">
              <CardContent className="p-6 text-sm text-destructive">{error}</CardContent>
            </Card>
          ) : companies.length === 0 ? (
            <Card className="max-w-2xl">
              <CardContent className="space-y-4 p-8 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-muted">
                  <Building2 className="h-6 w-6 text-muted-foreground" />
                </div>
                <div className="space-y-2">
                  <p className="font-medium">No companies yet</p>
                  <p className="text-sm text-muted-foreground">
                    Companies appear here after job discovery finds opportunities.
                    Run company research from opportunity details to enrich profiles.
                  </p>
                </div>
                <Button asChild variant="outline">
                  <Link href="/opportunities">View opportunities</Link>
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {companies.map((company) => (
                <CompanyCard
                  key={company.name}
                  company={company}
                  onSelect={setSelectedCompany}
                />
              ))}
            </div>
          )}
        </div>

        <CompanyDetailSheet
          company={selectedCompany}
          onClose={() => setSelectedCompany(null)}
        />
      </AppShell>
    </ProtectedRoute>
  );
}
