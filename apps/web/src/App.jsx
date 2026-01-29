import AppShell from "./components/layout/AppShell";
import LeftRail from "./components/layout/LeftRail";
import TopSpaceChips from "./components/layout/TopSpaceChips";
import CenterCanvas from "./components/layout/CenterCanvas";
import RightContext from "./components/layout/RightContext";
import BottomComposer from "./components/chat/BottomComposer";

export default function App() {
  return (
    <AppShell
      left={<LeftRail />}
      top={<TopSpaceChips />}
      center={<CenterCanvas />}
      right={<RightContext />}
      bottom={<BottomComposer />}
    />
  );
}
