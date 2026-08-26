import { Link, useNavigate } from "react-router-dom";

import { AuthForm } from "./AuthForm";

export function RegisterPage(): React.ReactElement {
  const navigate = useNavigate();
  return <><AuthForm mode="register" onSuccess={() => navigate("/projects", { replace: true })} /><p className="auth-switch">이미 계정이 있나요? <Link to="/login">로그인</Link></p></>;
}
