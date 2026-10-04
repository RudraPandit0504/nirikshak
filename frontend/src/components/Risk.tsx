import { useLang } from '../i18n'
import { LEVEL_HEX } from '../ui'

type Level = 'low' | 'medium' | 'high'

export function RiskPill({ level, score }: { level: Level; score: number }) {
  const { t } = useLang()
  return (
    <span
      className="glass-pill inline-flex h-7 shrink-0 items-center gap-1.5 whitespace-nowrap px-2.5 text-xs font-semibold text-ink"
      style={{ background: `color-mix(in oklab, ${LEVEL_HEX[level]} 22%, var(--glass-strong))` }}
    >
      <span className="size-2 rounded-full" style={{ background: LEVEL_HEX[level], boxShadow: `0 0 10px ${LEVEL_HEX[level]}` }} />
      <span className="font-mono tabular">{score}</span>
      <span className="text-ink-2">{t[`risk_${level}`]}</span>
    </span>
  )
}

/** Risk score as a glowing ring inside a glass orb. */
export function RiskGauge({ level, score, size = 168 }: { level: Level; score: number; size?: number }) {
  const { t } = useLang()
  const r = 54
  const c = 2 * Math.PI * r
  const arc = c * 0.78
  const color = LEVEL_HEX[level]
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <div className="glass absolute inset-0 rounded-full" style={{ borderRadius: '9999px' }} />
      <div className="absolute -inset-3 rounded-full opacity-40" style={{ background: `radial-gradient(closest-side, ${color}, transparent)` }} />
      <svg viewBox="0 0 128 128" className="absolute inset-0 -rotate-[230deg]">
        <circle cx="64" cy="64" r={r} fill="none" strokeWidth="9" strokeLinecap="round"
          stroke="var(--hairline)" strokeDasharray={`${arc} ${c}`} />
        <circle cx="64" cy="64" r={r} fill="none" strokeWidth="9" strokeLinecap="round" stroke={color}
          strokeDasharray={`${(arc * score) / 100} ${c}`}
          style={{ filter: `drop-shadow(0 0 6px ${color})`, transition: 'stroke-dasharray 1.2s var(--ease-out-soft)' }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="display tabular text-[3.25rem] leading-none">{score}</div>
          <div className="mt-1.5 text-[13px] font-semibold" style={{ color }}>{t[`risk_${level}`]}</div>
        </div>
      </div>
    </div>
  )
}
