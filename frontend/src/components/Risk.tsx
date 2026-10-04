import { useLang } from '../i18n'

const LEVEL = {
  low: { ring: 'text-emerald-500', pill: 'bg-emerald-500 text-white' },
  medium: { ring: 'text-amber-500', pill: 'bg-amber-400 text-slate-900' },
  high: { ring: 'text-red-500', pill: 'bg-red-500 text-white' },
}

export function RiskPill({ level, score }: { level: 'low' | 'medium' | 'high'; score: number }) {
  const { t } = useLang()
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold shadow ${LEVEL[level].pill}`}>
      {score} · {t[`risk_${level}`]}
    </span>
  )
}

export function RiskGauge({ level, score }: { level: 'low' | 'medium' | 'high'; score: number }) {
  const { t } = useLang()
  const r = 52
  const c = 2 * Math.PI * r
  const arc = c * 0.75
  return (
    <div className="relative size-40 shrink-0">
      <svg viewBox="0 0 120 120" className="size-full -rotate-[225deg]">
        <circle cx="60" cy="60" r={r} fill="none" strokeWidth="10" strokeLinecap="round"
          className="stroke-slate-200 dark:stroke-slate-800" strokeDasharray={`${arc} ${c}`} />
        <circle cx="60" cy="60" r={r} fill="none" strokeWidth="10" strokeLinecap="round" stroke="currentColor"
          className={`${LEVEL[level].ring} transition-all duration-700`} strokeDasharray={`${(arc * score) / 100} ${c}`} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="text-4xl font-extrabold tabular-nums">{score}</div>
          <div className={`text-sm font-semibold ${LEVEL[level].ring}`}>{t[`risk_${level}`]}</div>
        </div>
      </div>
    </div>
  )
}
