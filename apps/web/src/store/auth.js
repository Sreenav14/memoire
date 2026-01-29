import { create } from "zustand";

/**
 * Local-only auth store.
 * In production we can switch to httpOnly cookies for stronger security,
 * but this keeps your app working now with a clean migration path.
 */
export const useAuthStore = create((set) => ({
  token: localStorage.getItem("memoir_token") || "",
  setToken: (token) => {
    localStorage.setItem("memoir_token", token);
    set({ token });
  },
  clearToken: () => {
    localStorage.removeItem("memoir_token");
    set({ token: "" });
  },
}));
