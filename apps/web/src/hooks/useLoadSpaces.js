import { useEffect, useState } from "react";
import { fetchSpaces } from "../api/spaces";
import { useSpaceStore } from "../store/space";

export function useLoadSpaces() {
  const setSpaces = useSpaceStore((s) => s.setSpaces);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;

    (async () => {
      try {
        setLoading(true);
        setError("");
        const data = await fetchSpaces();

        // Expected shape: array of spaces
        // Each space: { id, name } (or similar)
        if (!alive) return;
        setSpaces(Array.isArray(data) ? data : data?.spaces || []);
      } catch (e) {
        if (!alive) return;
        setError(e.message || "Failed to load spaces");
      } finally {
        if (alive) setLoading(false);
      }
    })();

    return () => {
      alive = false;
    };
  }, [setSpaces]);

  return { loading, error };
}
