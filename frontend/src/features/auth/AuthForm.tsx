import { useState, type FormEvent } from "react";

import { ApiError } from "../../app/api";
import { useAuth } from "./AuthProvider";

interface AuthFormProps {
  mode: "login" | "register";
  onSuccess(): void;
}

export function AuthForm({ mode, onSuccess }: AuthFormProps): React.ReactElement {
  const { login, register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const isLogin = mode === "login";

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (isLogin) await login(email, password);
      else await register(email, password);
      onSuccess();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "잠시 후 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <p className="eyebrow">RFP LENS</p>
        <h1 id="auth-title">{isLogin ? "다시 오셨네요" : "분석 공간 만들기"}</h1>
        <p className="muted">
          {isLogin ? "제안서 준비 현황을 이어서 확인하세요." : "공고문 근거를 놓치지 않는 제안서 준비를 시작하세요."}
        </p>
        <form onSubmit={submit} noValidate>
          <label htmlFor="email">이메일</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
          <label htmlFor="password">비밀번호</label>
          <input
            id="password"
            type="password"
            autoComplete={isLogin ? "current-password" : "new-password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={8}
            required
          />
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit" disabled={submitting}>
            {submitting ? "처리 중…" : isLogin ? "로그인" : "계정 만들기"}
          </button>
        </form>
      </section>
    </main>
  );
}
