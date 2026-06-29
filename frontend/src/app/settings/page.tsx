"use client";

import { useCallback, useEffect, useState } from "react";

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
  opportunitiesApi,
  preferencesApi,
  type JobScheduleStatus,
  type UserPreferences,
} from "@/lib/api";
import { formatSalaryInrHint, usesInrSalaryContext } from "@/lib/onboarding";

const REMOTE_OPTIONS = [
  { value: "remote", label: "Remote only" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
  { value: "flexible", label: "Flexible" },
];

const SCHEDULE_INTERVAL_OPTIONS = [
  { value: "off", label: "Off", minutes: null },
  { value: "60", label: "Every 1 hour", minutes: 60 },
  { value: "240", label: "Every 4 hours", minutes: 240 },
  { value: "720", label: "Every 12 hours", minutes: 720 },
  { value: "1440", label: "Every 24 hours", minutes: 1440 },
] as const;

function formatScheduleTimestamp(value: string | null | undefined): string {
  if (!value) return "Not scheduled";
  return new Date(value).toLocaleString();
}

function intervalSelectValue(
  enabled: boolean,
  intervalMinutes: number | null,
): string {
  if (!enabled) return "off";
  const match = SCHEDULE_INTERVAL_OPTIONS.find(
    (opt) => opt.minutes === intervalMinutes,
  );
  return match ? String(match.minutes) : "60";
}

export default function SettingsPage() {
  const { user } = useAuth();
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [scheduleStatus, setScheduleStatus] = useState<JobScheduleStatus | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [scheduleSaving, setScheduleSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [scheduleSuccess, setScheduleSuccess] = useState(false);

  const loadPreferences = useCallback(async () => {
    const [preferences, status] = await Promise.all([
      preferencesApi.get(),
      opportunitiesApi.scheduleStatus(),
    ]);
    setPrefs(preferences);
    setScheduleStatus(status);
  }, []);

  useEffect(() => {
    loadPreferences()
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load preferences");
      })
      .finally(() => setLoading(false));
  }, [loadPreferences]);

  useEffect(() => {
    if (!prefs?.job_search_schedule_enabled) return;

    const refreshScheduleStatus = () => {
      opportunitiesApi
        .scheduleStatus()
        .then(setScheduleStatus)
        .catch(() => {
          /* keep last known status on transient poll failures */
        });
    };

    const intervalId = window.setInterval(refreshScheduleStatus, 30_000);
    return () => window.clearInterval(intervalId);
  }, [prefs?.job_search_schedule_enabled]);

  const updateField = <K extends keyof UserPreferences>(
    key: K,
    value: UserPreferences[K],
  ) => {
    if (prefs) setPrefs({ ...prefs, [key]: value });
  };

  const saveSchedule = async (enabled: boolean, intervalMinutes: number | null) => {
    setScheduleSaving(true);
    setScheduleError(null);
    setScheduleSuccess(false);
    try {
      const updated = await preferencesApi.update({
        job_search_schedule_enabled: enabled,
        job_search_schedule_interval_minutes: intervalMinutes,
      });
      setPrefs((current) => (current ? { ...current, ...updated } : updated));
      const status = await opportunitiesApi.scheduleStatus();
      setScheduleStatus(status);
      setScheduleSuccess(true);
    } catch (err) {
      setScheduleError(
        err instanceof ApiError ? err.message : "Failed to update schedule",
      );
    } finally {
      setScheduleSaving(false);
    }
  };

  const handleScheduleToggle = async (enabled: boolean) => {
    if (!prefs) return;
    const intervalMinutes = enabled
      ? prefs.job_search_schedule_interval_minutes ?? 60
      : null;
    setPrefs({
      ...prefs,
      job_search_schedule_enabled: enabled,
      job_search_schedule_interval_minutes: intervalMinutes,
    });
    await saveSchedule(enabled, intervalMinutes);
  };

  const handleScheduleIntervalChange = async (value: string) => {
    if (!prefs) return;
    const enabled = value !== "off";
    const intervalMinutes = enabled ? Number(value) : null;
    setPrefs({
      ...prefs,
      job_search_schedule_enabled: enabled,
      job_search_schedule_interval_minutes: intervalMinutes,
    });
    await saveSchedule(enabled, intervalMinutes);
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
  const lastRunAt =
    scheduleStatus?.last_run_at ?? prefs?.last_scheduled_run_at ?? null;
  const nextRunAt =
    scheduleStatus?.next_run_at ?? prefs?.next_scheduled_run_at ?? null;

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

            <Card>
              <CardHeader>
                <CardTitle>Scheduled Job Search</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <p className="text-sm text-muted-foreground">
                  Only fetches jobs posted since your last search.
                </p>

                {loading ? (
                  <p className="text-sm text-muted-foreground">Loading schedule...</p>
                ) : prefs ? (
                  <>
                    <div className="flex items-center justify-between gap-4">
                      <div className="space-y-1">
                        <Label htmlFor="schedule-enabled">
                          Enable automatic job discovery
                        </Label>
                        <p className="text-xs text-muted-foreground">
                          Runs search and evaluation on your chosen interval.
                        </p>
                      </div>
                      <input
                        id="schedule-enabled"
                        type="checkbox"
                        checked={prefs.job_search_schedule_enabled}
                        disabled={scheduleSaving}
                        onChange={(e) => void handleScheduleToggle(e.target.checked)}
                        className="h-4 w-4 rounded border border-input accent-primary"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="schedule-interval">Search interval</Label>
                      <select
                        id="schedule-interval"
                        value={intervalSelectValue(
                          prefs.job_search_schedule_enabled,
                          prefs.job_search_schedule_interval_minutes,
                        )}
                        disabled={scheduleSaving}
                        onChange={(e) =>
                          void handleScheduleIntervalChange(e.target.value)
                        }
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {SCHEDULE_INTERVAL_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-1">
                        <p className="text-sm font-medium">Last run</p>
                        <p className="text-sm text-muted-foreground">
                          {formatScheduleTimestamp(lastRunAt)}
                        </p>
                        {scheduleStatus?.last_run_summary ? (
                          <p className="text-xs text-muted-foreground">
                            {scheduleStatus.last_run_summary}
                          </p>
                        ) : null}
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm font-medium">Next run</p>
                        <p className="text-sm text-muted-foreground">
                          {prefs.job_search_schedule_enabled
                            ? formatScheduleTimestamp(nextRunAt)
                            : "Not scheduled"}
                        </p>
                      </div>
                    </div>

                    {scheduleError ? (
                      <p className="text-sm text-destructive">{scheduleError}</p>
                    ) : null}
                    {scheduleSuccess ? (
                      <p className="text-sm text-emerald-500">Schedule updated.</p>
                    ) : null}
                    {scheduleSaving ? (
                      <p className="text-sm text-muted-foreground">Saving schedule...</p>
                    ) : null}
                  </>
                ) : (
                  <p className="text-sm text-destructive">
                    {error ?? "Could not load schedule settings."}
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
