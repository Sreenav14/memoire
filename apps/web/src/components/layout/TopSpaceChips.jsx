const spaces = [
    "Personal",
    "Work",
    "Research",
    "Ideas",
  ];
  
  export default function TopSpaceChips() {
    return (
      <div className="flex items-center gap-2 px-4 py-3 overflow-x-auto">
        {spaces.map((space, i) => (
          <button
            key={space}
            className={`px-3 py-1.5 rounded-full text-sm border ${
              i === 0
                ? "bg-white/10 border-white/20"
                : "border-white/10 opacity-70 hover:opacity-100"
            }`}
          >
            {space}
          </button>
        ))}
  
        <button className="px-3 py-1.5 rounded-full text-sm border border-dashed border-white/20 opacity-60 hover:opacity-100">
          + New
        </button>
      </div>
    );
  }
  