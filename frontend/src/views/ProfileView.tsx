import { useEffect, useState } from 'react'
import { ArrowLeft, ExternalLink, Flame, Loader2, Play, Printer, ShieldAlert } from 'lucide-react'
import { fmtTime, getProfile } from '../api'
import { useLang } from '../i18n'
import type { Category, Meta, Profile } from '../types'
import RegistryCard from '../components/RegistryCard'
import { RiskGauge, RiskPill } from '../components/Risk'
import Glass from '../components/ui/Glass'
import { Button, LinkButton } from '../components/ui/Button'
import { CAT_COLOR, LEVEL_HEX } from '../ui'

const ORDER: Category[] = ['guaranteed_returns', 'stock_tip', 'price_prediction', 'paid_group', 'paid_promotion',
  'urgency_fomo', 'misleading_claim', 'registration_claim']

export default function ProfileView({ id, meta }: { id: string; meta: Meta | null }) {
  const { t, lang } = useLang()
  const [p, setP] = useState<Profile | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    getProfile(id).then(setP).catch((e) => setErr(e.message))
  }, [id])

  if (err) return <Glass className="mx-auto mt-16 max-w-md p-8 text-center text-ink">{err}</Glass>
  if (!p) return <Loader2 className="mx-auto mt-24 size-8 animate-spin text-ink-3" />

  const n = p.videos.length
  const cat = (c: Category) => meta?.categories[c]?.[lang] ?? c
  const high = p.videos.filter((v) => v.risk_level === 'high').length
  const color = LEVEL_HEX[p.level]
  const inVideos = (k: number) => t.inVideos.replace('{k}', String(k)).replace('{n}', String(n))
  const initials = p.channel.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()

  const stats = [
    [t.videosAudited, String(n)],
    [t.medianRisk, `${Math.round(p.median_risk)}/100`],
    [t.highRiskVideos, `${high}/${n}`],
    [t.disclaimerRate, `${Math.round(p.disclaimer_rate * 100)}%`],
  ]

  return (
    <div className="mx-auto max-w-[1200px] px-4 pt-6 sm:px-6 sm:pt-8">
      <a href="#/" className="no-print mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-3 transition hover:text-ink">
        <ArrowLeft className="size-4" /> {t.backHome}
      </a>

      {/* Hero */}
      <Glass strong className="overflow-hidden p-6 sm:p-8">
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full opacity-25 blur-3xl" style={{ background: color }} />
        <div className="relative flex flex-col gap-7 md:flex-row md:items-center">
          <RiskGauge level={p.level} score={Math.round(p.median_risk)} />
          <div className="min-w-0 flex-1">
            <p className="eyebrow">{t.profileTitle}</p>
            <div className="mt-2 flex items-center gap-3">
              <span className="grid size-12 shrink-0 place-items-center rounded-full bg-[linear-gradient(135deg,#ff9500,#c644fc)] text-lg font-bold text-white shadow-[inset_0_1px_0_rgba(255,255,255,.45)]">
                {initials}
              </span>
              <h1 className="display min-w-0 truncate text-[clamp(1.6rem,3.2vw,2.4rem)] leading-tight">{p.channel}</h1>
            </div>
            <p className="mt-4 text-lg font-semibold leading-snug" lang={lang} style={{ color: `color-mix(in oklab, ${color} 70%, var(--ink))` }}>
              {p.headline[lang]}
            </p>
            <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {stats.map(([label, value]) => (
                <div key={label} className="glass-inset px-3.5 py-3">
                  <div className="display tabular text-2xl">{value}</div>
                  <div className="mt-0.5 text-xs text-ink-3">{label}</div>
                </div>
              ))}
            </div>
            <div className="no-print mt-5 flex flex-wrap gap-2">
              <LinkButton href={p.channel_url} target="_blank" rel="noreferrer"><ExternalLink className="size-4" /> {t.openChannel}</LinkButton>
              <Button variant="ghost" onClick={() => window.print()}><Printer className="size-4" /> {t.print}</Button>
            </div>
          </div>
        </div>
      </Glass>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-5">
          {/* Category frequency */}
          <Glass className="p-6">
            <p className="eyebrow">{t.howOften}</p>
            <ul className="mt-4 space-y-3.5">
              {ORDER.map((c) => {
                const k = p.category_videos[c] ?? 0
                return (
                  <li key={c}>
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="flex items-center gap-2 font-medium text-ink"><span className={`size-2 rounded-full ${CAT_COLOR[c]}`} />{cat(c)}</span>
                      <span className={`tabular text-xs ${k ? 'font-semibold text-ink' : 'text-ink-3'}`}>{k ? inVideos(k) : t.noFlags}</span>
                    </div>
                    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[var(--hairline)]">
                      <div className={`h-full rounded-full ${CAT_COLOR[c]} transition-[width] duration-700 ease-[var(--ease-out-soft)]`}
                        style={{ width: `${(k / n) * 100}%` }} />
                    </div>
                  </li>
                )
              })}
            </ul>
          </Glass>

          {/* Risk across videos */}
          <Glass className="p-6">
            <div className="flex items-baseline justify-between">
              <p className="eyebrow">{t.riskTrend}</p>
              <p className="text-xs text-ink-3">← {t.newest} · {t.oldest} →</p>
            </div>
            <div className="mt-5 flex h-40 items-end gap-2">
              {p.videos.map((v) => (
                <a key={v.report_id} href={`#/report/${v.report_id}`} title={`${v.risk_score} · ${v.title}`}
                  className="group flex h-full flex-1 flex-col items-center justify-end gap-1.5">
                  <span className="tabular text-[11px] font-semibold text-ink-2">{v.risk_score}</span>
                  <span className="w-full max-w-12 rounded-t-xl rounded-b-md transition-all duration-500 ease-[var(--ease-spring)] group-hover:brightness-110"
                    style={{
                      height: `${Math.max(4, v.risk_score)}%`, background: `linear-gradient(180deg, ${LEVEL_HEX[v.risk_level]}, color-mix(in oklab, ${LEVEL_HEX[v.risk_level]} 55%, transparent))`,
                      boxShadow: `0 6px 18px -8px ${LEVEL_HEX[v.risk_level]}`,
                    }} />
                </a>
              ))}
            </div>
          </Glass>

          {/* Worst moments */}
          {p.worst.length > 0 && (
            <Glass className="p-6">
              <p className="eyebrow flex items-center gap-1.5"><Flame className="size-3.5" /> {t.worstMoments}</p>
              <ul className="mt-4 space-y-3">
                {p.worst.map((w, i) => (
                  <li key={i} className="glass-inset p-4">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <a href={`#/report/${w.report_id}/t/${Math.floor(w.start)}`}
                        className="inline-flex h-7 items-center gap-1 rounded-full bg-[var(--ink)] px-2.5 font-mono font-medium text-[var(--bg)] transition active:scale-95">
                        <Play className="size-3" fill="currentColor" /> {fmtTime(w.start)}
                      </a>
                      <span className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-ink">
                        <span className={`size-2 rounded-full ${CAT_COLOR[w.category]}`} /> {cat(w.category)}
                      </span>
                      <span className="min-w-0 truncate text-ink-3">· {w.video_title}</span>
                    </div>
                    <blockquote className="mt-3 border-l-[3px] border-[#ff9500] pl-3.5 text-[15px] font-medium leading-relaxed text-ink">“{w.quote}”</blockquote>
                    <p className="mt-2 text-sm leading-relaxed text-ink-2" lang={lang}>{lang === 'hi' && w.why_hi ? w.why_hi : w.why_en}</p>
                  </li>
                ))}
              </ul>
            </Glass>
          )}
        </div>

        <aside className="space-y-5 order-first lg:order-none">
          <RegistryCard registry={p.registry} />
          <Glass className="p-6">
            <p className="eyebrow flex items-center gap-1.5"><ShieldAlert className="size-3.5" /> {t.verifyReport}</p>
            <ul className="mt-3 space-y-2.5 text-sm leading-relaxed text-ink-2">
              <li>{t.todo1}</li>
              <li>{t.todo3}</li>
            </ul>
          </Glass>
        </aside>
      </div>

      {/* Audited videos */}
      <section className="mt-10">
        <h2 className="display mb-5 text-2xl">{t.auditedVideos}</h2>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {p.videos.map((v) => (
            <a key={v.report_id} href={`#/report/${v.report_id}`} className="glass glass-hover group block overflow-hidden p-2">
              <div className="relative aspect-video overflow-hidden rounded-[20px]">
                <img src={`https://i.ytimg.com/vi/${v.video_id}/mqdefault.jpg`} alt="" loading="lazy"
                  className="size-full object-cover transition-transform duration-700 group-hover:scale-[1.04]" />
                <div className="absolute left-2.5 top-2.5"><RiskPill level={v.risk_level} score={v.risk_score} /></div>
              </div>
              <p className="line-clamp-2 px-2 pb-2 pt-3 text-sm font-semibold leading-snug text-ink">{v.title}</p>
              {v.categories.length > 0 && (
                <div className="flex flex-wrap gap-1 px-2 pb-2">
                  {v.categories.map((c) => <span key={c} title={cat(c)} className={`size-2 rounded-full ${CAT_COLOR[c]}`} />)}
                </div>
              )}
            </a>
          ))}
        </div>
      </section>
    </div>
  )
}
