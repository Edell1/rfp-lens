import { Link, useNavigate } from "react-router-dom";

import { AuthForm } from "./AuthForm";

export function LoginPage(): React.ReactElement {
  const navigate = useNavigate();
  return <><AuthForm mode="login" onSuccess={() => navigate("/projects", { replace: true })} /><p className="auth-switch">처음이신가요? <Link to="/register">계정 만들기</Link></p></>;
}
