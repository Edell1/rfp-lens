import type { AnalysisOverview, OverviewFallbackRequirement, RequirementRecord, SourceLocator, SummaryHighlight } from "../../app/api";

export const coreCategoryOrder = ["eligibility", "budget", "schedule", "submission", "evaluation", "technical_goal"] as const;
export const overviewCategoryLabels: Record<string, string> = { eligibility: "지원 자격", exclusion: "제외 조건", budget: "예산", schedule: "일정", submission: "제출", evaluation: "평가", technical_goal: "기술 목표", quantitative_target: "정량 목표", other: "기타" };

export function overviewPollingInterval(data: AnalysisOverview | undefined): number | false {
  return data && ["pending", "running"].includes(data.summary_state) ? 2_000 : false;
}

export interface LinkedRequirement { id: string; text: string; category: string; mandatory: boolean; review_state: string; evidence: Array<{ quote: string; verified: boolean; locator: SourceLocator }>; }

export function linkedRequirements(highlight: SummaryHighlight | undefined, requirements: RequirementRecord[] | undefined): LinkedRequirement[] {
  if (!highlight || !requirements) return [];
  const ids = new Set(highlight.requirement_ids);
  return requirements.filter((item) => ids.has(item.id));
}

export function fallbackAsHighlights(items: OverviewFallbackRequirement[]): SummaryHighlight[] {
  return Object.keys(overviewCategoryLabels).flatMap((category) => {
    const grouped = items.filter((item) => item.category === category);
    return grouped.length ? [{ category: category as SummaryHighlight["category"], headline: `${overviewCategoryLabels[category]} 요구사항 ${grouped.length}건`, detail: "AI 요약 대신 추출된 원문 요구사항을 표시합니다.", requirement_ids: grouped.map((item) => item.id) }] : [];
  });
}
