"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Download, FileText, Mail } from "lucide-react";

import { materialDisplayContent } from "@/components/opportunities/opportunity-utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { resumeApi, type ApplicationMaterial } from "@/lib/api";
import { cn } from "@/lib/utils";

import { downloadMaterialPdf } from "@/components/workflows/workflow-material-utils";

interface WorkflowMaterialResultProps {
  materialId: string;
  highlighted?: boolean;
}

function materialTitle(material: ApplicationMaterial) {
  return material.material_type === "cover_letter" ? "Cover letter ready" : "Tailored resume ready";
}

function materialIcon(material: ApplicationMaterial) {
  return material.material_type === "cover_letter" ? (
    <Mail className="h-4 w-4 text-primary" />
  ) : (
    <FileText className="h-4 w-4 text-primary" />
  );
}

export function WorkflowMaterialResult({
  materialId,
  highlighted = false,
}: WorkflowMaterialResultProps) {
  const [material, setMaterial] = useState<ApplicationMaterial | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void resumeApi
      .materials()
      .then((materials) => {
        if (cancelled) return;
        const found = materials.find((item) => item.id === materialId);
        if (found) {
          setMaterial(found);
          setError(null);
        } else {
          setError("Generated material could not be loaded.");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Generated material could not be loaded.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [materialId]);

  if (error) {
    return (
      <Card className="border-destructive/30 bg-destructive/5">
        <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
      </Card>
    );
  }

  if (!material) {
    return (
      <Card className="border-primary/30 bg-primary/5">
        <CardContent className="p-4 text-sm text-muted-foreground">Loading material...</CardContent>
      </Card>
    );
  }

  return (
    <Card
      id={`workflow-material-${material.id}`}
      className={cn(
        "border-primary/30 bg-primary/5 transition-shadow",
        highlighted && "ring-2 ring-primary/50",
      )}
    >
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          {materialIcon(material)}
          {materialTitle(material)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {material.opportunity_title} at {material.opportunity_company}
        </p>
        <div className="max-h-64 overflow-y-auto rounded-lg border border-border/60 bg-background/80 p-4 text-sm whitespace-pre-wrap">
          {materialDisplayContent(material)}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            disabled={downloading}
            onClick={() => {
              setDownloading(true);
              void downloadMaterialPdf(material).finally(() => setDownloading(false));
            }}
          >
            <Download className="h-4 w-4" />
            {downloading ? "Downloading..." : "Download PDF"}
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href={material.material_type === "cover_letter" ? "/opportunities" : "/resume"}>
              {material.material_type === "cover_letter"
                ? "Open opportunities"
                : "Open resume workspace"}
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
