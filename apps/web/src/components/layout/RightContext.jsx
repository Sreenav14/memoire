export default function RightContext() {
    return (
      <div className="h-full p-4">
        <div className="text-sm font-semibold mb-3">
          Cortex Active Context
        </div>
  
        <div className="space-y-3 text-xs opacity-80">
          <div className="panel p-3">
            Memory used: Design notes
          </div>
          <div className="panel p-3">
            Memory used: API architecture
          </div>
          <div className="panel p-3">
            Memory used: Vector search idea
          </div>
        </div>
      </div>
    );
  }
  