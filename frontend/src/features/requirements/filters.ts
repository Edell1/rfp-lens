import type { RequirementCategory, ReviewState } from "../../app/api";

export const categoryLabels: Record<RequirementCategory, string> = {
  eligibility: "지원 자격", exclusion: "제외 대상", schedule: "일정", budget: "예산",
  submission: "제출", technical_goal: "기술 목표", quantitative_target: "정량 목표",
  evaluation: "평가", other: "기타",
};

export const reviewLabels: Record<ReviewState, string> = {
  pending: "검토 대기", confirmed: "확정", rejected: "제외", edited: "수정됨",
};
