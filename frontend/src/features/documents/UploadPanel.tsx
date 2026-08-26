import { useRef, useState } from "react";

const maxUploadBytes = 26_214_400;
const allowedExtensions = [".pdf", ".hwpx"];

interface UploadPanelProps {
  onUpload(file: File): Promise<void>;
  isUploading: boolean;
}

function extensionOf(name: string): string {
  const index = name.lastIndexOf(".");
  return index === -1 ? "" : name.slice(index).toLowerCase();
}

export function UploadPanel({ onUpload, isUploading }: UploadPanelProps): React.ReactElement {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File | undefined): Promise<void> {
    if (!file) return;
    const extension = extensionOf(file.name);
    if (!allowedExtensions.includes(extension)) {
      setError("PDF 또는 HWPX 파일만 업로드할 수 있습니다. 기존 HWP 파일은 지원하지 않습니다.");
      return;
    }
    if (file.size > maxUploadBytes) {
      setError("파일 크기는 25MiB 이하여야 합니다.");
      return;
    }
    setError(null);
    try {
      await onUpload(file);
      if (inputRef.current) inputRef.current.value = "";
    } catch {
      setError("업로드에 실패했습니다. 파일을 확인한 뒤 다시 시도해 주세요.");
    }
  }

  return <section className="upload-panel" aria-labelledby="upload-title">
    <div><p className="eyebrow">NEW SOURCE</p><h2 id="upload-title">공고문 추가</h2><p className="muted">PDF 또는 HWPX · 최대 25MiB · HWP는 지원하지 않음</p></div>
    <label className="file-picker" htmlFor="rfp-file">파일 선택
      <input ref={inputRef} id="rfp-file" type="file" accept=".pdf,.hwpx,application/pdf,application/hwp+zip" onChange={(event) => void handleFile(event.target.files?.[0])} disabled={isUploading} />
    </label>
    {isUploading && <p role="status">업로드 중…</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </section>;
}
