import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api, type AiProvider } from "../../app/api";

const providerLabels: Record<AiProvider, string> = {
  openai: "OpenAI 클라우드",
  local: "로컬 모델 (Ollama 등)",
  fake: "합성 테스트 (demo 전용)",
};

export function AnalysisSettingsPage(): React.ReactElement {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["analysis-settings"], queryFn: api.getAnalysisSettings });
  const [provider, setProvider] = useState<AiProvider>("openai");
  const [openaiModel, setOpenaiModel] = useState("");
  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [localBaseUrl, setLocalBaseUrl] = useState("");
  const [localModel, setLocalModel] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!settings.data) return;
    setProvider(settings.data.ai_provider);
    setOpenaiModel(settings.data.openai_model);
    setLocalBaseUrl(settings.data.local_base_url);
    setLocalModel(settings.data.local_model);
  }, [settings.data]);

  const save = useMutation({
    mutationFn: () =>
      api.patchAnalysisSettings({
        ai_provider: provider,
        openai_model: openaiModel.trim() || undefined,
        openai_api_key: openaiApiKey.trim() || undefined,
        local_base_url: localBaseUrl.trim() || undefined,
        local_model: localModel.trim() || undefined,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["analysis-settings"], data);
      setOpenaiApiKey("");
      setSaved(true);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setSaved(false);
    save.mutate();
  }

  return <main className="app-shell"><header className="topbar"><Link to="/projects" className="brand">RFP <em>Lens</em></Link><Link to="/projects" className="text-button">프로젝트 목록</Link></header>
    <section className="page-heading compact"><p className="eyebrow">ANALYSIS SETTINGS</p><h1>분석 엔진 설정</h1><p>공고문 요구사항을 추출할 AI 공급자를 선택합니다. 저장 즉시 다음 분석부터 적용됩니다.</p></section>
    {settings.isLoading && <p>설정을 불러오는 중…</p>}
    {settings.isError && <p className="form-error" role="alert">설정을 불러오지 못했습니다.</p>}
    {settings.data && <section className="create-project" aria-labelledby="settings-form-title"><form onSubmit={submit}>
      <h2 id="settings-form-title">공급자 설정</h2>
      <label htmlFor="provider-select">분석 엔진<select id="provider-select" value={provider} onChange={(event) => setProvider(event.target.value as AiProvider)}>
        {(Object.keys(providerLabels) as AiProvider[]).map((value) => <option key={value} value={value}>{providerLabels[value]}</option>)}
      </select></label>
      {provider === "local" && <>
        <label htmlFor="local-base-url">로컬 서버 주소<input id="local-base-url" value={localBaseUrl} onChange={(event) => setLocalBaseUrl(event.target.value)} placeholder="http://host.docker.internal:11434/v1" /></label>
        <label htmlFor="local-model">로컬 모델명<input id="local-model" value={localModel} onChange={(event) => setLocalModel(event.target.value)} placeholder="qwen2.5:7b" required /></label>
      </>}
      {provider === "openai" && <>
        <label htmlFor="openai-model">OpenAI 모델<input id="openai-model" value={openaiModel} onChange={(event) => setOpenaiModel(event.target.value)} placeholder="gpt-5-mini" /></label>
        <label htmlFor="openai-api-key">OpenAI API 키{settings.data.openai_api_key_set && <span className="muted"> · 저장된 키 사용 중</span>}<input id="openai-api-key" type="password" autoComplete="off" value={openaiApiKey} onChange={(event) => setOpenaiApiKey(event.target.value)} placeholder={settings.data.openai_api_key_set ? "변경 시에만 입력" : "sk-…"} /></label>
      </>}
      {provider === "fake" && <p className="muted">합성 문구만 인식하는 오프라인 데모 모드입니다. demo 환경에서만 사용할 수 있습니다.</p>}
      {save.isError && <p className="form-error" role="alert">{save.error instanceof Error ? save.error.message : "저장하지 못했습니다."}</p>}
      {saved && save.isSuccess && <p role="status">설정이 저장되었습니다.</p>}
      <button type="submit" disabled={save.isPending}>{save.isPending ? "저장 중…" : "저장"}</button>
    </form></section>}
  </main>;
}
