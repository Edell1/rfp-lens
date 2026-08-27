import type { OverviewStats as Stats } from "../../app/api";

export function OverviewStats({ stats }: { stats: Stats }): React.ReactElement {
  const entries = [["전체 요구사항", stats.total], ["확정·수정", stats.confirmed_or_edited], ["검토 대기", stats.pending], ["근거 확인 필요", stats.unverified_evidence]] as const;
  return <section className="overview-stats" aria-label="분석 통계">{entries.map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}</section>;
}
