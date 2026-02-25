import { createBrowserRouter } from "react-router-dom";
import LoginPage from "../pages/LoginPage";
import SignupPage from "../pages/SignupPage";
import AppPage from "../pages/AppPage";
import RequireAuth from "./requireAuth";


export const router = createBrowserRouter([
    { path: "/", element: <LoginPage /> },
    { path: "/login", element: <LoginPage /> },
    { path: "/signup", element: <SignupPage /> },
    {
        path: "/app",
        element: (
          <RequireAuth>
            <AppPage />
          </RequireAuth>
        ),
      },
    ]);