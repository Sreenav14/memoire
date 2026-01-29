export default function BottomComposer() {
    return (
      <div className="p-4 flex items-center gap-3">
        <textarea
          placeholder="Ask Memoir… (type / to save)"
          rows={1}
          className="flex-1 resize-none bg-transparent border border-white/10 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-white/30"
        />
        <button className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-sm">
          Send
        </button>
      </div>
    );
  }
  