import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";

import { createQueryClient } from "./app/query-client";
import { AppRouter } from "./app/router";
import { AuthProvider } from "./features/auth/AuthProvider";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode><QueryClientProvider client={createQueryClient()}><BrowserRouter><AuthProvider><AppRouter /></AuthProvider></BrowserRouter></QueryClientProvider></StrictMode>,
);
