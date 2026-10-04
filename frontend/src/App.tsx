import { useEffect, useMemo, useState } from 'react'
import { ScanSearch } from 'lucide-react'
import { getMeta } from './api'
import { LangContext, STRINGS } from './i18n'
import type { Lang, Meta } from './types'
import Home from './views/Home'
import Job from './views/Job'
import ReportView from './views/ReportView'

type Route = { name: 'home' } | { name: 'job'; id: string } | { name: 'report'; id: string }

function parse(hash: string): Route {
  const [, kind, id] = hash.replace(/^#/, '').split('/')
  if (kind === 'job' && id) return { name: 'job', id }
  if (kind === 'report' && id) return { name: 'report', id }
  return { name: 'home' }
}

function initialLang(): Lang {
  const q = new URLSearchParams(window.location.search).get('lang')
  if (q === 'en' || q === 'hi') return q
  try {
    const v = localStorage.getItem('nirikshak-lang')
    if (v === 'en' || v === 'hi') return v
  } catch {
    /* storage unavailable */
  }
  return 'en'
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash))
  const [lang, setLangState] = useState<Lang>(initialLang)
  const [meta, setMeta] = useState<Meta | null>(null)

  useEffect(() => {
    const on = () => {
      setRoute(parse(window.location.hash))
      window.scrollTo({ top: 0 })
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  useEffect(() => {
    getMeta().then(setMeta).catch(() => setMeta(null))
  }, [])

  const setLang = (l: Lang) => {
    setLangState(l)
    try {
      localStorage.setItem('nirikshak-lang', l)
    } catch {
      /* ignore */
    }
  }
  const ctx = useMemo(() => ({ lang, t: STRINGS[lang], setLang }), [lang])

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  return (
    <LangContext.Provider value={ctx}>
      <div className="min-h-screen flex flex-col">
        <header className="no-print sticky top-0 z-20 border-b border-slate-200/70 dark:border-slate-800/70 bg-white/80 dark:bg-slate-950/80 backdrop-blur">
          <div className="mx-auto max-w-7xl px-4 h-14 flex items-center justify-between gap-3">
            <a href="#/" className="flex items-center gap-2.5 min-w-0">
              <span className="grid place-items-center size-8 rounded-lg bg-slate-900 dark:bg-amber-400 text-amber-400 dark:text-slate-900">
                <ScanSearch className="size-5" />
              </span>
              <span className="font-extrabold tracking-tight text-lg">
                Nirikshak <span className="font-semibold text-slate-400" lang="hi">निरीक्षक</span>
              </span>
              <span className="hidden md:inline text-sm text-slate-500 truncate">· {ctx.t.tagline}</span>
            </a>
            <div className="flex items-center gap-3">
              {meta && (
                <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-400">
                  <span className="size-1.5 rounded-full bg-emerald-500" />
                  {meta.model} · {meta.registry_size.toLocaleString('en-IN')} SEBI entities
                </span>
              )}
              <div className="flex rounded-lg border border-slate-200 dark:border-slate-800 p-0.5 text-sm">
                {(['en', 'hi'] as Lang[]).map((l) => (
                  <button
                    key={l}
                    onClick={() => setLang(l)}
                    className={`px-2.5 py-1 rounded-md font-medium transition ${
                      lang === l ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900' : 'text-slate-500 hover:text-slate-900 dark:hover:text-white'
                    }`}
                  >
                    {l === 'en' ? 'EN' : 'हिं'}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1">
          {route.name === 'home' && <Home />}
          {route.name === 'job' && <Job id={route.id} />}
          {route.name === 'report' && <ReportView id={route.id} meta={meta} />}
        </main>

        <footer className="no-print border-t border-slate-200 dark:border-slate-800 py-6 px-4 text-center text-xs text-slate-500 max-w-3xl mx-auto">
          {ctx.t.footer}
        </footer>
      </div>
    </LangContext.Provider>
  )
}
