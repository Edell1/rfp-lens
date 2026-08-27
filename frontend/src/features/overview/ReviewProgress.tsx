import type { OverviewStats } from "../../app/api";

export function ReviewProgress({ stats }: { stats: OverviewStats }): React.ReactElement {
  const reviewable = Math.max(stats.total - stats.rejected, 0);
  const percent = reviewable ? Math.round((stats.confirmed_or_edited / reviewable) * 100) : 0;
  return <aside className="review-progress"><p className="eyebrow">REVIEW PROGRESS</p><h2>검토 진행률 {percent}%</h2><div className="progress-track" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${percent}%` }} /></div><dl><div><dt>확정·수정</dt><dd>{stats.confirmed_or_edited}</dd></div><div><dt>검토 대기</dt><dd>{stats.pending}</dd></div><div><dt>제외</dt><dd>{stats.rejected}</dd></div></dl>{stats.unverified_evidence > 0 && <p className="progress-notice">원문 근거 확인이 필요한 요구사항 {stats.unverified_evidence}건</p>}</aside>;
}
