import { create } from "zustand";

const KEY = "memoir_active_space_id";

export const useSpaceStore = create((set) => ({
  spaces: [],
  activeSpaceId: localStorage.getItem(KEY) || "",
  setSpaces: (spaces) =>
    set((s) => {
      // If we don't have an active space, pick the first
      const nextActive =
        s.activeSpaceId || (spaces?.[0]?.id ? String(spaces[0].id) : "");
      if (nextActive) localStorage.setItem(KEY, nextActive);
      return { spaces, activeSpaceId: nextActive };
    }),
  setActiveSpaceId: (id) => {
    const v = String(id || "");
    localStorage.setItem(KEY, v);
    set({ activeSpaceId: v });
  },
}));
