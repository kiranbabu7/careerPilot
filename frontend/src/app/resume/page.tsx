"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, FileText } from "lucide-react";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { ResumeUpload } from "@/components/profile/resume-upload";
import { ScoreCard } from "@/components/profile/score-card";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, resumeApi, type Resume } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function ResumePage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [uploadMessage, setUploadMessage] = useState<string | null>(null);

  const loadResumes = useCallback(async () => {
    try {
      const data = await resumeApi.list();
      setResumes(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load resumes");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadResumes();
  }, [loadResumes]);

  const activeResume = resumes.find((r) => r.is_active) ?? resumes[0] ?? null;
  const analysis = activeResume?.latest_analysis ?? null;

  const handleUpload = async (file: File) => {
    setUploadMessage(null);
    const result = await resumeApi.upload(file);
    if (result.profile_enriched) {
      const fields = result.fields_updated?.join(", ") ?? "profile fields";
      setUploadMessage(
        `CareerPilot updated your profile from this resume (${fields}). Return to Home to see your refreshed profile completion.`,
      );
    } else {
      setUploadMessage("Resume uploaded and analyzed. Your existing preferences were kept.");
    }
    await loadResumes();
  };

  const handleSetActive = async (id: string) => {
    await resumeApi.setActive(id);
    await loadResumes();
  };

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="p-8">
          <div className="mx-auto max-w-4xl space-y-6">
            <div>
              <h1 className="text-2xl font-semibold">Resume workspace</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Upload your resume for AI-powered health and ATS scoring. CareerPilot
                will enrich your profile from the analysis when fields are still empty.
              </p>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Upload resume</CardTitle>
              </CardHeader>
              <CardContent>
                <ResumeUpload onUpload={handleUpload} />
                {uploadMessage ? (
                  <p className="mt-3 text-sm text-primary">{uploadMessage}</p>
                ) : null}
              </CardContent>
            </Card>

            {loading ? (
              <p className="text-sm text-muted-foreground">Loading resumes...</p>
            ) : error ? (
              <p className="text-sm text-destructive">{error}</p>
            ) : activeResume && analysis ? (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <ScoreCard
                    title="Resume health"
                    score={analysis.health_score}
                    description="Structure, clarity, and impact"
                  />
                  <ScoreCard
                    title="ATS compatibility"
                    score={analysis.ats_score}
                    description="Keyword and format alignment"
                  />
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Active resume</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="font-medium">{activeResume.original_filename}</p>
                        <p className="text-xs text-muted-foreground">
                          Analyzed with {analysis.model_name}
                        </p>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground">{analysis.raw_summary}</p>
                  </CardContent>
                </Card>

                <div className="grid gap-4 md:grid-cols-2">
                  <InsightList title="Strengths" items={analysis.strengths} variant="positive" />
                  <InsightList title="Weaknesses" items={analysis.weaknesses} variant="negative" />
                  <InsightList title="Missing keywords" items={analysis.missing_keywords} />
                  <InsightList title="Suggestions" items={analysis.improvement_suggestions} />
                </div>

                {analysis.extracted_skills.length > 0 ? (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">Extracted skills</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-2">
                        {analysis.extracted_skills.map((skill) => (
                          <span
                            key={skill}
                            className="rounded-md bg-muted px-2 py-1 text-sm"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                ) : null}
              </>
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-sm text-muted-foreground">
                  No resume uploaded yet. Drop a PDF, DOCX, or TXT file above to get
                  your first AI analysis.
                </CardContent>
              </Card>
            )}

            {resumes.length > 1 ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Resume versions</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {resumes.map((resume) => (
                      <li
                        key={resume.id}
                        className={cn(
                          "flex items-center justify-between rounded-lg border px-4 py-3",
                          resume.is_active ? "border-primary/40 bg-primary/5" : "border-border",
                        )}
                      >
                        <div className="flex items-center gap-2">
                          {resume.is_active ? (
                            <CheckCircle2 className="h-4 w-4 text-primary" />
                          ) : (
                            <FileText className="h-4 w-4 text-muted-foreground" />
                          )}
                          <div>
                            <p className="text-sm font-medium">
                              {resume.original_filename}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {new Date(resume.created_at).toLocaleDateString()}
                              {resume.latest_analysis
                                ? ` · Health ${resume.latest_analysis.health_score}`
                                : ""}
                            </p>
                          </div>
                        </div>
                        {!resume.is_active ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => void handleSetActive(resume.id)}
                          >
                            Set active
                          </Button>
                        ) : (
                          <span className="text-xs text-primary">Active</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}

function InsightList({
  title,
  items,
  variant,
}: {
  title: string;
  items: string[];
  variant?: "positive" | "negative";
}) {
  if (items.length === 0) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {items.map((item) => (
            <li
              key={item}
              className={cn(
                "text-sm",
                variant === "positive" && "text-emerald-500",
                variant === "negative" && "text-amber-500",
                !variant && "text-muted-foreground",
              )}
            >
              {item}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
