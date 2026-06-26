"use client";

import { useEffect, useState } from "react";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { AppShell } from "@/components/layout/app-shell";
import { TagInput } from "@/components/ui/tag-input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/auth-context";
import {
  ApiError,
  preferencesApi,
  type UserPreferences,
} from "@/lib/api";
import { formatSalaryInrHint, usesInrSalaryContext } from "@/lib/onboarding";

const REMOTE_OPTIONS = [
  { value: "remote", label: "Remote only" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
  { value: "flexible", label: "Flexible" },
];

export default function SettingsPage() {
  const { user } = useAuth();
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    preferencesApi
      .get()
      .then(setPrefs)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load preferences");
      })
      .finally(() => setLoading(false));
  }, []);

  const updateField = <K extends keyof UserPreferences>(
    key: K,
    value: UserPreferences[K],
  ) => {
    if (prefs) setPrefs({ ...prefs, [key]: value });
  };

  const handleSave = async () => {
    if (!prefs) return;
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await preferencesApi.update({
        target_roles: prefs.target_roles,
        target_locations: prefs.target_locations,
        salary_min: prefs.salary_min,
        salary_max: prefs.salary_max,
        remote_preference: prefs.remote_preference,
        career_goals: prefs.career_goals,
        skills: prefs.skills,
      });
      setPrefs(updated);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save preferences");
    } finally {
      setSaving(false);
    }
  };

  const inrSalaryContext = usesInrSalaryContext(
    prefs?.salary_min ?? null,
    prefs?.salary_max ?? null,
  );
  const salaryUnitLabel = inrSalaryContext ? "INR" : "USD";

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="p-8">
          <div className="mx-auto max-w-2xl space-y-6">
            <div>
              <h1 className="text-2xl font-semibold">Career preferences</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Tell CareerPilot about your goals so resume analysis and future agents
                can personalize recommendations.
              </p>
            </div>

            {user ? (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Account</CardTitle>
                </CardHeader>
                <CardContent className="text-sm">
                  <p className="font-medium">{user.full_name}</p>
                  <p className="text-muted-foreground">{user.email}</p>
                </CardContent>
              </Card>
            ) : null}

            <Card>
              <CardHeader>
                <CardTitle>Your career profile</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {loading ? (
                  <p className="text-sm text-muted-foreground">Loading preferences...</p>
                ) : prefs ? (
                  <>
                    <div className="space-y-2">
                      <Label>Target roles</Label>
                      <TagInput
                        value={prefs.target_roles}
                        onChange={(tags) => updateField("target_roles", tags)}
                        placeholder="e.g. Senior Backend Engineer"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label>Target locations</Label>
                      <TagInput
                        value={prefs.target_locations}
                        onChange={(tags) => updateField("target_locations", tags)}
                        placeholder="e.g. Remote, Austin, NYC"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="remote">Remote preference</Label>
                      <select
                        id="remote"
                        value={prefs.remote_preference}
                        onChange={(e) =>
                          updateField("remote_preference", e.target.value)
                        }
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {REMOTE_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="salary_min">Salary min ({salaryUnitLabel})</Label>
                        <Input
                          id="salary_min"
                          type="number"
                          value={prefs.salary_min ?? ""}
                          onChange={(e) =>
                            updateField(
                              "salary_min",
                              e.target.value ? Number(e.target.value) : null,
                            )
                          }
                          placeholder={inrSalaryContext ? "2600000" : "120000"}
                        />
                        {inrSalaryContext && prefs.salary_min ? (
                          <p className="text-xs text-muted-foreground">
                            ≈ {formatSalaryInrHint(prefs.salary_min)} per annum
                          </p>
                        ) : null}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="salary_max">Salary max ({salaryUnitLabel})</Label>
                        <Input
                          id="salary_max"
                          type="number"
                          value={prefs.salary_max ?? ""}
                          onChange={(e) =>
                            updateField(
                              "salary_max",
                              e.target.value ? Number(e.target.value) : null,
                            )
                          }
                          placeholder={inrSalaryContext ? "3000000" : "180000"}
                        />
                        {inrSalaryContext && prefs.salary_max ? (
                          <p className="text-xs text-muted-foreground">
                            ≈ {formatSalaryInrHint(prefs.salary_max)} per annum
                          </p>
                        ) : null}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label>Skills</Label>
                      <TagInput
                        value={prefs.skills}
                        onChange={(tags) => updateField("skills", tags)}
                        placeholder="e.g. Python, React, AWS"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="goals">Career goals</Label>
                      <textarea
                        id="goals"
                        value={prefs.career_goals}
                        onChange={(e) => updateField("career_goals", e.target.value)}
                        placeholder="What does your next career move look like?"
                        className="min-h-[100px] w-full resize-none rounded-lg border border-input bg-background px-4 py-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      />
                    </div>

                    {error ? (
                      <p className="text-sm text-destructive">{error}</p>
                    ) : null}
                    {success ? (
                      <p className="text-sm text-emerald-500">Preferences saved.</p>
                    ) : null}

                    <Button onClick={handleSave} disabled={saving}>
                      {saving ? "Saving..." : "Save preferences"}
                    </Button>
                  </>
                ) : (
                  <p className="text-sm text-destructive">
                    {error ?? "Could not load preferences."}
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
