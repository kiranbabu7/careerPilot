"use client";

import type { Application } from "@/lib/api";

import { ApplicationColumn } from "./application-column";

interface ApplicationBoardProps {
  stageOrder: string[];
  stages: Record<string, Application[]>;
  onSelect: (id: string) => void;
}

export function ApplicationBoard({
  stageOrder,
  stages,
  onSelect,
}: ApplicationBoardProps) {
  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {stageOrder.map((stage) => (
        <ApplicationColumn
          key={stage}
          stage={stage}
          applications={stages[stage] ?? []}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
