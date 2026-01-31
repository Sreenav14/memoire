import { createBrowserRouter } from "react-router-dom";
import LoginPage from "../pages/LoginPage";
import AppPage from "../pages/AppPage";
import RequireAuth from "./requireAuth";


export const router = createBrowserRouter([
    { path: "/", element: <LoginPage /> },
    { path: "/login", element: <LoginPage /> },
    {
        path: "/app",
        element: (
          <RequireAuth>
            <AppPage />
          </RequireAuth>
        ),
      },
    ]);