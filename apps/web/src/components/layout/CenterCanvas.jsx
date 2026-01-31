export default function CenterCanvas() {
  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-lg font-semibold">Memories</div>
          <div className="text-sm text-white/60">Notes, saved chat, decisions</div>
        </div>
        <button className="rounded-xl bg-white/10 hover:bg-white/15 px-3 py-2 text-sm">
          New memory
        </button>
      </div>

      <div className="divide-y divide-white/10 rounded-2xl border border-white/10 bg-white/5">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="px-4 py-3 hover:bg-white/5 transition">
            <div className="text-sm font-medium">Memory item #{i + 1}</div>
            <div className="text-xs text-white/60 mt-1 line-clamp-2">
              Short preview of the content will appear here. This is a placeholder for notes and saved snippets.
            </div>
            <div className="text-[11px] text-white/40 mt-2">
              Note • 2 days ago
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
