export default function RightContext() {
  return (
    <div className="p-4">
      <div className="text-sm font-semibold mb-3">Details</div>

      <div className="space-y-3">
        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <div className="text-xs text-white/60">Active space</div>
          <div className="text-sm mt-1">Personal</div>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <div className="text-xs text-white/60">Selected memory</div>
          <div className="text-sm mt-1 text-white/50">None</div>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <div className="text-xs text-white/60">Tips</div>
          <div className="text-xs text-white/50 mt-1">
            Use Chat to ask questions and see citations here.
          </div>
        </div>
      </div>
    </div>
  );
}
