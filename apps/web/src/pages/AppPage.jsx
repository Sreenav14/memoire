import AppShell from "../components/layout/AppShell";
import LeftRail from "../components/layout/LeftRail";
import TopSpaceChips from "../components/layout/TopSpaceChips";
import CenterCanvas from "../components/layout/CenterCanvas";
import RightContext from "../components/layout/RightContext";
import BottomComposer from "../components/chat/BottomComposer";
import { useLoadSpaces } from "../hooks/useLoadSpaces";

export default function AppPage() {
  const { loading, error } = useLoadSpaces();

  return (
    <AppShell
      left={<LeftRail />}
      top={<TopSpaceChips />}
      center={
        <div>
          {loading && (
            <div className="px-6 pt-4 text-sm opacity-70">Loading spaces...</div>
          )}
          {error && (
            <div className="px-6 pt-4 text-sm text-red-300">{error}</div>
          )}
          <CenterCanvas />
        </div>
      }
      right={<RightContext />}
      bottom={<BottomComposer />}
    />
  );
}
