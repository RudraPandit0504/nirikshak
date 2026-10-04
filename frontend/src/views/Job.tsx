import { useEffect, useState } from 'react'
import { AlertTriangle, Check, Loader2 } from 'lucide-react'
import { watchJob } from '../api'
import { go } from '../ui'
import { useLang } from '../i18n'
import type { Strings } from '../i18n'

const STAGES = ['fetch', 'transcribe', 'scan', 'analyse', 'registry', 'summary'] as const
type Stage = (typeof STAGES)[number]

export default function Job({ id }: { id: string }) {
  const { t } = useLang()
  const [stage, setStage] = useState<Stage | null>(null)
  const [frac, setFrac] = useState(0)
  const [msgs, setMsgs] = useState<Partial<Record<Stage, string>>>({})
  const [queued, setQueued] = useState(false)
  const [error, setError] = useState('')

  useEffect(
    () =>
      watchJob(id, (ev) => {
        if (ev.type === 'queued') setQueued(ev.position > 0)
        else if (ev.type === 'progress') {
          setQueued(false)
          setStage(ev.stage as Stage)
          setFrac(ev.frac)
          setMsgs((m) => ({ ...m, [ev.stage]: ev.msg }))
        } else if (ev.type === 'done') go(`/report/${ev.id}`)
        else if (ev.type === 'error') setError(ev.msg)
      }),
    [id],
  )

  const current = stage ? STAGES.indexOf(stage) : -1
  const overall = Math.round(((Math.max(current, 0) + (stage ? frac : 0)) / STAGES.length) * 100)

  return (
    <div className="mx-auto max-w-xl px-4 py-16">
      <h1 className="text-2xl font-bold">{error ? t.failed : queued ? t.queued : t.working}</h1>
      {!error && (
        <div className="mt-4 h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
          <div className="h-full bg-amber-400 transition-all duration-500" style={{ width: `${overall}%` }} />
        </div>
      )}

      <ol className="mt-8 space-y-1">
        {STAGES.map((s, i) => {
          const done = i < current || (i === current && frac >= 1)
          const active = i === current && !done
          return (
            <li key={s} className={`flex items-start gap-3 rounded-lg px-3 py-2.5 ${active ? 'bg-white dark:bg-slate-900 shadow-sm' : ''}`}>
              <span
                className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full text-xs ${
                  done ? 'bg-emerald-500 text-white' : active ? 'bg-amber-400 text-slate-900' : 'bg-slate-200 dark:bg-slate-800 text-slate-500'
                }`}
              >
                {done ? <Check className="size-3.5" /> : active && !error ? <Loader2 className="size-3.5 animate-spin" /> : i + 1}
              </span>
              <div className="min-w-0">
                <p className={`font-medium ${!done && !active ? 'text-slate-400' : ''}`}>{t[`stage_${s}` as keyof Strings] as string}</p>
                {msgs[s] && <p className="text-sm text-slate-500 truncate">{msgs[s]}</p>}
              </div>
            </li>
          )
        })}
      </ol>

      {error && (
        <div className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <p className="flex items-start gap-2 text-red-700 dark:text-red-400">
            <AlertTriangle className="size-5 shrink-0" /> {error}
          </p>
          <a href="#/" className="mt-3 inline-block font-semibold underline">
            {t.tryAgain}
          </a>
        </div>
      )}
    </div>
  )
}
