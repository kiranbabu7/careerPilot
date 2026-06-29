"use client";

import type { InterviewPlanContent } from "@/lib/api";

const SECTION_LABELS: Record<string, string> = {
  prep_roadmap: "Prep roadmap",
  likely_questions: "Likely questions",
  system_design_topics: "System design topics",
  company_talking_points: "Company talking points",
  resume_stories: "Resume stories",
  gaps_to_practice: "Gaps to practice",
};

interface PrepSectionRendererProps {
  content: InterviewPlanContent;
}

export function PrepSectionRenderer({ content }: PrepSectionRendererProps) {
  const sections = Object.entries(SECTION_LABELS).map(([key, label]) => ({
    key,
    label,
    items: content[key as keyof InterviewPlanContent],
  }));

  return (
    <div className="space-y-6">
      {sections.map(({ key, label, items }) => {
        if (!items || !Array.isArray(items) || items.length === 0) return null;
        return (
          <section key={key} className="space-y-2">
            <h3 className="text-sm font-semibold">{label}</h3>
            <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
              {items.map((item, index) => (
                <li key={`${key}-${index}`}>
                  {typeof item === "string" ? item : JSON.stringify(item)}
                </li>
              ))}
            </ul>
          </section>
        );
      })}

      {content.day_by_day_checklist && content.day_by_day_checklist.length > 0 ? (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold">Day-by-day checklist</h3>
          <div className="space-y-3">
            {content.day_by_day_checklist.map((day) => (
              <div
                key={day.day}
                className="rounded-lg border border-border bg-muted/20 px-3 py-2"
              >
                <p className="text-sm font-medium">Day {day.day}</p>
                <ul className="mt-1 list-inside list-disc text-sm text-muted-foreground">
                  {day.tasks.map((task) => (
                    <li key={task}>{task}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
