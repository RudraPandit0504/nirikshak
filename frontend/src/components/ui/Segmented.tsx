import type { ReactNode } from 'react'

/** iOS-style segmented control: a glass capsule with a sliding highlighted thumb. */
export default function Segmented<T extends string>({
  options, value, onChange, size = 'md', className = '', label,
}: {
  options: { value: T; label: ReactNode }[]
  value: T
  onChange: (v: T) => void
  size?: 'sm' | 'md'
  className?: string
  label?: string
}) {
  const i = Math.max(0, options.findIndex((o) => o.value === value))
  const h = size === 'sm' ? 'h-8 text-[13px]' : 'h-10 text-sm'
  return (
    <div role="tablist" aria-label={label} className={`glass-pill inline-flex p-1 ${className}`}>
      <div className="relative grid w-full" style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
        <span
          aria-hidden
          className="absolute inset-y-0 rounded-full bg-[var(--glass-strong)] shadow-[inset_0_1px_0_rgba(255,255,255,.7),0_2px_10px_-2px_rgba(15,23,42,.25)] transition-transform duration-500 ease-[var(--ease-spring)]"
          style={{ width: `${100 / options.length}%`, transform: `translateX(${i * 100}%)` }}
        />
        {options.map((o) => (
          <button
            key={o.value}
            role="tab"
            aria-selected={o.value === value}
            onClick={() => onChange(o.value)}
            className={`relative z-10 inline-flex items-center justify-center gap-1.5 px-3.5 font-semibold rounded-full transition-colors ${h} ${
              o.value === value ? 'text-ink' : 'text-ink-3 hover:text-ink-2'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}
