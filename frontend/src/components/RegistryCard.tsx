import { AlertTriangle, BadgeCheck, BadgeX, ExternalLink, ShieldQuestion } from 'lucide-react'
import { useLang } from '../i18n'
import type { RegistryCheck } from '../types'
import Glass from './ui/Glass'

const SEBI_RA = 'https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=14'

export default function RegistryCard({ registry: r }: { registry: RegistryCheck }) {
  const { t } = useLang()
  const good = r.verdict === 'verified' || r.verdict === 'matched' || r.verdict === 'guests_registered'
  const bad = ['number_not_found', 'not_registered', 'claimed_unverified', 'registered_other'].includes(r.verdict)
  const Icon = good ? BadgeCheck : bad ? BadgeX : ShieldQuestion
  const color = good ? '#34c759' : bad ? '#ff3b30' : '#ff9f0a'
  const typo = Object.values(r.number_results).some((h) => h && h.score < 100)
  const checks = r.checks ?? []
  return (
    <Glass className="p-6">
      <p className="eyebrow">{t.registry}</p>
      <div className="mt-4 flex items-start gap-3 rounded-[20px] p-4"
        style={{ background: `color-mix(in oklab, ${color} 13%, transparent)`, boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${color} 25%, transparent)` }}>
        <Icon className="size-6 shrink-0" style={{ color }} />
        <div className="min-w-0">
          <p className="font-semibold text-ink">{r.verdict === 'verified' && typo ? t.verifiedTypo : t.verdict[r.verdict]}</p>
          {r.entity && (
            <p className="mt-1 text-sm font-medium text-ink">
              {r.entity.name} · {t.catNames[r.entity.category] ?? r.entity.category}{' '}
              <span className="font-mono text-xs text-ink-3">{r.entity.reg_no}</span>
            </p>
          )}
          <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{t.verdictHelp[r.verdict]}</p>
        </div>
      </div>

      {checks.length > 0 ? (
        <div className="mt-5">
          <p className="eyebrow">{t.checked}</p>
          <ul className="mt-3 space-y-2.5 text-sm">
            {checks.map((c, i) => {
              const h = c.hits[0]
              return (
                <li key={i} className="flex gap-2.5">
                  {h ? <BadgeCheck className="mt-0.5 size-4 shrink-0 text-[#34c759]" /> : <BadgeX className="mt-0.5 size-4 shrink-0 text-ink-3" />}
                  <div className="min-w-0">
                    <p className="truncate">
                      <span className={c.kind === 'name' ? 'font-semibold text-ink' : 'font-mono text-xs text-ink'}>{c.query}</span>
                      <span className="text-xs text-ink-3"> · {t.roles[c.role] ?? c.role}</span>
                    </p>
                    <p className="truncate text-xs text-ink-3">
                      {h ? (
                        <>
                          {h.how === 'near_number' && <span className="text-[#ff9f0a]">{t.typoMatch} </span>}
                          {h.name} · {t.catNames[h.category] ?? h.category} <span className="font-mono">{h.reg_no}</span>
                        </>
                      ) : t.notInRegister}
                    </p>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      ) : (
        r.numbers_found.length > 0 && (
          <div className="mt-5">
            <p className="eyebrow">{t.numbersQuoted}</p>
            <ul className="mt-2 space-y-1.5 text-sm">
              {r.numbers_found.map((n) => {
                const hit = r.number_results[n]
                return (
                  <li key={n} className="flex flex-wrap items-center gap-x-2">
                    {hit ? <BadgeCheck className="size-4 text-[#34c759]" /> : <BadgeX className="size-4 text-[#ff3b30]" />}
                    <span className="font-mono text-ink">{n}</span>
                    {hit && <span className="truncate text-ink-3">· {hit.name}</span>}
                  </li>
                )
              })}
            </ul>
          </div>
        )
      )}

      <div className="mt-5 flex items-center justify-between border-t hairline pt-4 text-sm">
        <span className="text-ink-2">{t.disclaimer}</span>
        <span className="inline-flex items-center gap-1 font-semibold" style={{ color: r.disclaimer_found ? '#34c759' : '#ff9f0a' }}>
          {r.disclaimer_found ? <BadgeCheck className="size-4" /> : <AlertTriangle className="size-4" />}
          {r.disclaimer_found ? t.disclaimerYes : t.disclaimerNo}
        </span>
      </div>
      <a className="link mt-4 text-sm" href={SEBI_RA} target="_blank" rel="noreferrer">
        {t.verifyOn} <ExternalLink className="size-3.5" />
      </a>
    </Glass>
  )
}
