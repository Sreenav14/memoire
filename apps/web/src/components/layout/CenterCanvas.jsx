export default function CenterCanvas() {
    return (
      <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="panel p-4 hover:translate-y-[-2px] transition"
          >
            <div className="text-sm font-medium">
              Memory Item #{i + 1}
            </div>
            <div className="text-xs opacity-70 mt-2">
              This is a placeholder for notes, decisions,
              or saved chat snippets.
            </div>
          </div>
        ))}
      </div>
    );
  }
  