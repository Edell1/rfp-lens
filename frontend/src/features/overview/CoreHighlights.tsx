import type { SummaryHighlight } from "../../app/api";
import { coreCategoryOrder, overviewCategoryLabels } from "./overview";

export function CoreHighlights({ highlights, selected, onSelect }: { highlights: SummaryHighlight[]; selected?: SummaryHighlight; onSelect(item: SummaryHighlight): void }): React.ReactElement | null {
  const ordered = highlights.filter((item) => coreCategoryOrder.includes(item.category as never)).sort((left, right) => coreCategoryOrder.indexOf(left.category as never) - coreCategoryOrder.indexOf(right.category as never));
  if (!ordered.length) return null;
  return <section className="core-highlights" aria-labelledby="core-highlights-title"><p className="eyebrow">CORE CONDITIONS</p><h2 id="core-highlights-title">핵심 조건</h2><div className="highlight-grid">{ordered.map((item) => <button type="button" className={`highlight-card ${selected === item ? "selected" : ""}`} key={`${item.category}-${item.headline}`} onClick={() => onSelect(item)}><span>{overviewCategoryLabels[item.category as keyof typeof overviewCategoryLabels] ?? item.category}</span><strong>{item.headline}</strong><small>{item.detail}</small><em>연결 요구사항 {item.requirement_ids.length}건</em></button>)}</div></section>;
}
