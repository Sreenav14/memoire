import {
    Home,
    FileText,
    MessageSquare,
    Book,
    Settings,
  } from "lucide-react";
  
  const items = [
    { icon: Home, label: "Spaces" },
    { icon: FileText, label: "Notes" },
    { icon: MessageSquare, label: "Chat" },
    { icon: Book, label: "Docs" },
    { icon: Settings, label: "About" },
  ];
  
  export default function LeftRail() {
    return (
      <div className="h-full flex flex-col items-center py-4 gap-4">
        <div className="text-xs font-semibold opacity-70 mb-2">Memoir</div>
  
        {items.map(({ icon: Icon, label }) => (
          <button
            key={label}
            className="w-10 h-10 flex items-center justify-center rounded-xl hover:bg-white/5 transition"
            title={label}
          >
            <Icon size={18} />
          </button>
        ))}
      </div>
    );
  }
  