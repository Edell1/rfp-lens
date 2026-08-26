import { useState } from "react";

import { api } from "../../app/api";

export function ExportButton({ projectId }: { projectId: string }): React.ReactElement {
  const [downloading, setDownloading] = useState(false);
  async function download(): Promise<void> {
    setDownloading(true);
    try {
      const content = await api.downloadCompliance(projectId);
      const url = URL.createObjectURL(content);
      const link = document.createElement("a");
      link.href = url;
      link.download = "compliance.xlsx";
      link.click();
      URL.revokeObjectURL(url);
    } finally { setDownloading(false); }
  }
  return <button onClick={() => void download()} disabled={downloading}>{downloading ? "내보내는 중…" : "Excel 내보내기"}</button>;
}
