import type { ReactNode } from 'react'

export default function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium transition-all duration-300 ease-[var(--ease-spring)] active:scale-95 ${
        on
          ? 'bg-[var(--ink)] text-[var(--bg)] shadow-[0_6px_16px_-8px_rgba(15,23,42,.6)]'
          : 'glass-pill text-ink-2 hover:text-ink'
      }`}
    >
      {children}
    </button>
  )
}
