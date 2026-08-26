import type { DocumentRecord } from "../../app/api";

interface ProcessingStatusProps {
  document: DocumentRecord;
  onRetry(document: DocumentRecord): void;
  isRetrying: boolean;
}

const labels: Record<DocumentRecord["state"], string> = {
  uploaded: "업로드됨",
  parsing: "문서를 읽고 있어요",
  analyzing: "요구사항을 분석하고 있어요",
  review_required: "검토할 요구사항이 준비됐어요",
  completed: "검토가 완료됐어요",
  partial: "일부 항목만 분석됐어요",
  failed: "처리에 실패했어요",
  ocr_required: "OCR이 필요한 문서예요",
};

export function isPollingState(state: DocumentRecord["state"]): boolean {
  return ["uploaded", "parsing", "analyzing"].includes(state);
}

export function ProcessingStatus({ document, onRetry, isRetrying }: ProcessingStatusProps): React.ReactElement {
  if (document.state === "uploaded") {
    return <div className="status-card"><strong>분석을 시작할 준비가 됐어요</strong><button onClick={() => onRetry(document)} disabled={isRetrying}>분석 시작</button></div>;
  }
  if (document.state === "ocr_required") {
    return <div className="status-card warning" role="status"><strong>텍스트가 없는 스캔 PDF입니다</strong><span>텍스트 PDF 또는 HWPX로 다시 업로드해 주세요</span></div>;
  }
  if (document.state === "partial") {
    return <div className="status-card warning" role="status"><strong>일부 요구사항만 추출됐습니다</strong><span>근거가 누락된 항목은 원문을 확인해 주세요.</span><button onClick={() => onRetry(document)} disabled={isRetrying}>다시 분석</button></div>;
  }
  if (document.state === "failed") {
    return <div className="status-card error" role="status"><strong>문서 처리가 완료되지 않았습니다</strong><span>{document.error_message ?? "잠시 후 다시 시도해 주세요."}</span><button onClick={() => onRetry(document)} disabled={isRetrying}>다시 시도</button></div>;
  }
  return <span className={`status-pill ${isPollingState(document.state) ? "working" : ""}`}>{labels[document.state]}</span>;
}
