import { materialDisplayContent } from "@/components/opportunities/opportunity-utils";
import { resumeApi, type ApplicationMaterial } from "@/lib/api";

export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function materialFilenamePrefix(material: ApplicationMaterial) {
  const slug = material.opportunity_title.replace(/\s+/g, "-").toLowerCase().slice(0, 40);
  return material.material_type === "cover_letter"
    ? `cover-letter-${slug}`
    : `tailored-resume-${slug}`;
}

export async function downloadMaterialPdf(material: ApplicationMaterial) {
  const prefix = materialFilenamePrefix(material);
  try {
    const blob = await resumeApi.downloadMaterialPdf(material.id);
    downloadBlob(`${prefix}.pdf`, blob);
  } catch {
    downloadBlob(
      `${prefix}.txt`,
      new Blob([materialDisplayContent(material)], { type: "text/plain;charset=utf-8" }),
    );
  }
}

export async function downloadMaterialPdfById(materialId: string) {
  const materials = await resumeApi.materials();
  const material = materials.find((item) => item.id === materialId);
  if (!material) {
    throw new Error("Generated material not found.");
  }
  await downloadMaterialPdf(material);
}

export const MATERIAL_VIEW_ACTION_KEYS = new Set([
  "view_tailored_resume",
  "view_cover_letter",
]);

export const MATERIAL_DOWNLOAD_ACTION_KEYS = new Set([
  "download_tailored_resume",
  "download_cover_letter",
]);

/** Actions handled in the UI (scroll/open/download) — not chat quick replies. */
export const LINK_ONLY_WORKFLOW_ACTION_KEYS = new Set([
  "view_interview_prep",
  ...MATERIAL_VIEW_ACTION_KEYS,
  ...MATERIAL_DOWNLOAD_ACTION_KEYS,
]);

export function scrollToElementInScrollArea(element: HTMLElement | null): boolean {
  if (!element) return false;

  const viewport = element.closest("[data-radix-scroll-area-viewport]");
  if (viewport instanceof HTMLElement) {
    const elementTop = element.getBoundingClientRect().top;
    const viewportTop = viewport.getBoundingClientRect().top;
    const nextTop = viewport.scrollTop + (elementTop - viewportTop) - 16;
    viewport.scrollTo({ top: Math.max(0, nextTop), behavior: "smooth" });
    return true;
  }

  element.scrollIntoView({ behavior: "smooth", block: "start" });
  return true;
}
