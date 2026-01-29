export default function AppShell({
    left,
    top,
    center,
    right,
    bottom,
  }) {
    return (
        <div className="h-screen grid grid-cols-[64px_1fr_360px] grid-rows-[auto_1fr_auto] bg-[var(--color-memoir-bg)]">
          {/* Left rail */}
          <aside className="row-span-3 border-r border-[var(--color-memoir-stroke)]">
            {left}
          </aside>
          {/* Top bar */}
          <header className="border-b border-[var(--color-memoir-stroke)]">
            {top}
          </header>
          {/* Center canvas */}
          <main className="overflow-auto">
            {center}
          </main>
          {/* Right context */}
          <aside className="row-span-2 border-l border-[var(--color-memoir-stroke)]">
            {right}
          </aside>
          {/* Bottom composer */}
          <footer className="col-span-2 border-t border-[var(--color-memoir-stroke)]">
            {bottom}
          </footer>
        </div>
      );
  }
  