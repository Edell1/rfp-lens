import type { SummaryHighlight } from "../../app/api";
import { coreCategoryOrder, overviewCategoryLabels } from "./overview";

export function AdditionalHighlights({ highlights, selected, onSelect }: { highlights: SummaryHighlight[]; selected?: SummaryHighlight; onSelect(item: SummaryHighlight): void }): React.ReactElement | null {
  const additional = highlights.filter((item) => !coreCategoryOrder.includes(item.category as never));
  if (!additional.length) return null;
  return <section className="additional-highlights" aria-labelledby="additional-highlights-title"><p className="eyebrow">ADDITIONAL ITEMS</p><h2 id="additional-highlights-title">추가 검토 항목</h2><div>{additional.map((item) => <button type="button" className={selected === item ? "selected" : ""} key={`${item.category}-${item.headline}`} onClick={() => onSelect(item)}><span>{overviewCategoryLabels[item.category] ?? item.category}</span><strong>{item.headline}</strong><em>{item.requirement_ids.length}건</em></button>)}</div></section>;
}
