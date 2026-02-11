export default function AppShell({
    left,
    top,
    center,
    right,
    // bottom,
    
  }) {
    return (
      <div className="h-screen grid grid-cols-[72px_1fr_340px] grid-rows-[56px_1fr] bg-[#0B0F14] text-white">
      <aside className="row-span-2 border-r border-white/10">{left}</aside>
      <header className="col-span-2 border-b border-white/10">{top}</header>
      <main className="overflow-auto">
      <div className="min-h-full">{center}</div>
      </main>

      <aside className="overflow-auto border-l border-white/10 bg-white/5">
      {right}
      </aside>
    </div>
      );
  }
  