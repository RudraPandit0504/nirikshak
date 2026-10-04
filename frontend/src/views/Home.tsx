import { useEffect, useRef, useState } from 'react'
import { ArrowRight, FileAudio, Loader2, Lock, Upload } from 'lucide-react'
import { listReports, startUpload, startUrl } from '../api'
import { go } from '../ui'
import { useLang } from '../i18n'
import type { ReportListItem } from '../types'
import { RiskPill } from '../components/Risk'

export default function Home() {
  const { t } = useLang()
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [recent, setRecent] = useState<ReportListItem[] | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    listReports().then(setRecent).catch(() => setRecent([]))
  }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    setBusy(true)
    setErr('')
    try {
      const { job } = await startUrl(url.trim())
      go(`/job/${job}`)
    } catch (ex) {
      setErr((ex as Error).message)
      setBusy(false)
    }
  }

  const upload = async (f: File) => {
    setBusy(true)
    setErr('')
    try {
      const { job } = await startUpload(f)
      go(`/job/${job}`)
    } catch (ex) {
      setErr((ex as Error).message)
      setBusy(false)
    }
  }

  return (
    <div>
      <section className="relative overflow-hidden border-b border-slate-200 dark:border-slate-800">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,rgba(251,191,36,0.15),transparent_60%)]" />
        <div className="mx-auto max-w-3xl px-4 py-16 sm:py-24 text-center">
          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight">{t.heroTitle}</h1>
          <p className="mt-5 text-base sm:text-lg text-slate-600 dark:text-slate-400 leading-relaxed">{t.heroSub}</p>

          <form onSubmit={submit} className="mt-8 flex flex-col sm:flex-row gap-2">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder={t.urlPlaceholder}
              inputMode="url"
              className="flex-1 min-w-0 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3.5 text-base outline-none focus:ring-2 focus:ring-amber-400"
            />
            <button
              disabled={busy}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 dark:bg-amber-400 px-6 py-3.5 font-semibold text-white dark:text-slate-900 hover:opacity-90 disabled:opacity-60"
            >
              {busy ? <Loader2 className="size-5 animate-spin" /> : <ArrowRight className="size-5" />}
              {t.audit}
            </button>
          </form>

          <div className="mt-4 flex items-center justify-center gap-3 text-sm text-slate-500">
            <span>{t.or}</span>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-slate-300 dark:border-slate-700 px-3 py-1.5 hover:border-amber-400 hover:text-slate-900 dark:hover:text-white"
            >
              <Upload className="size-4" /> {t.upload}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="audio/*,video/*,.opus,.ogg,.m4a"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            />
          </div>
          <p className="mt-1 text-xs text-slate-400">{t.uploadHint}</p>

          {err && <p className="mt-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-600 dark:text-red-400">{err}</p>}

          <p className="mt-8 inline-flex items-center gap-2 text-xs text-slate-500">
            <Lock className="size-3.5" /> {t.privacy}
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-10">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-4">{t.recent}</h2>
        {recent === null ? (
          <Loader2 className="size-5 animate-spin text-slate-400" />
        ) : recent.length === 0 ? (
          <p className="text-slate-500">{t.noRecent}</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {recent.map((r) => (
              <a
                key={r.id}
                href={`#/report/${r.id}`}
                className="group rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden hover:border-amber-400 transition"
              >
                <div className="relative aspect-video bg-slate-200 dark:bg-slate-800">
                  {r.video_id ? (
                    <img src={`https://i.ytimg.com/vi/${r.video_id}/mqdefault.jpg`} alt="" className="size-full object-cover" loading="lazy" />
                  ) : (
                    <div className="grid size-full place-items-center text-slate-400">
                      <FileAudio className="size-10" />
                    </div>
                  )}
                  <div className="absolute top-2 left-2">
                    <RiskPill level={r.risk_level} score={r.risk_score} />
                  </div>
                </div>
                <div className="p-3">
                  <p className="font-medium leading-snug line-clamp-2 group-hover:text-amber-600 dark:group-hover:text-amber-400">{r.title}</p>
                  <p className="mt-1 text-xs text-slate-500 truncate">{r.channel}</p>
                </div>
              </a>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
