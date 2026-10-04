import { useEffect, useMemo, useState } from 'react'
import { Monitor, Moon, ScanSearch, Sun } from 'lucide-react'
import { getMeta } from './api'
import { LangContext, STRINGS } from './i18n'
import type { Lang, Meta } from './types'
import Backdrop from './components/Backdrop'
import Segmented from './components/ui/Segmented'
import { useTheme, type ThemePref } from './components/ui/theme'
import Home from './views/Home'
import Job from './views/Job'
import ReportView from './views/ReportView'
import ProfileView from './views/ProfileView'

type Route = { name: 'home' } | { name: 'job'; id: string } | { name: 'report'; id: string; t?: number } | { name: 'profile'; id: string }

function parse(hash: string): Route {
  const [, kind, id, sub, val] = hash.replace(/^#/, '').split('/')
  if (kind === 'job' && id) return { name: 'job', id }
  if (kind === 'report' && id) return { name: 'report', id, t: sub === 't' && val ? Number(val) : undefined }
  if (kind === 'profile' && id) return { name: 'profile', id }
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
  const [theme, setTheme] = useTheme()

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
  const t = ctx.t

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const themeIcon = { system: Monitor, light: Sun, dark: Moon }
  const nextTheme: Record<ThemePref, ThemePref> = { system: 'light', light: 'dark', dark: 'system' }
  const ThemeIcon = themeIcon[theme]
  const themeName = { system: t.themeSystem, light: t.themeLight, dark: t.themeDark }[theme]

  return (
    <LangContext.Provider value={ctx}>
      <Backdrop />
      <div className="min-h-screen flex flex-col">
        {/* Floating navigation capsule */}
        <header className="no-print sticky top-0 z-30 px-3 pt-3 sm:px-6 sm:pt-4">
          <nav className="glass-pill mx-auto flex h-14 max-w-[1200px] items-center justify-between gap-2 pl-2 pr-2 sm:pl-3">
            <a href="#/" className="flex min-w-0 items-center gap-2.5 rounded-full pr-2">
              <span className="relative grid size-10 place-items-center rounded-full bg-[linear-gradient(135deg,#ff9500,#ff5e3a_55%,#c644fc)] text-white shadow-[inset_0_1px_0_rgba(255,255,255,.5),0_6px_16px_-6px_rgba(255,94,58,.7)]">
                <ScanSearch className="size-5" strokeWidth={2.2} />
              </span>
              <span className="display text-[17px] leading-none">
                Nirikshak
                <span className="ml-1.5 font-hindi text-[15px] font-semibold text-ink-3" lang="hi">निरीक्षक</span>
              </span>
            </a>

            <div className="flex items-center gap-1.5 sm:gap-2">
              {meta && (
                <span className="hidden lg:inline-flex h-8 items-center gap-2 rounded-full px-3 text-xs font-medium text-ink-2 bg-[var(--glass-inset)]">
                  <span className="relative flex size-2">
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-[#34c759] opacity-60" />
                    <span className="relative inline-flex size-2 rounded-full bg-[#34c759]" />
                  </span>
                  {t.localBadge} · <span className="font-mono">{meta.model}</span> · {meta.registry_size.toLocaleString('en-IN')} {t.sebiEntities}
                </span>
              )}
              <button
                onClick={() => setTheme(nextTheme[theme])}
                title={themeName}
                aria-label={themeName}
                className="grid size-9 place-items-center rounded-full text-ink-2 transition hover:bg-[var(--glass-inset)] hover:text-ink"
              >
                <ThemeIcon className="size-[18px]" />
              </button>
              <Segmented
                size="sm"
                label="Language"
                value={lang}
                onChange={setLang}
                options={[{ value: 'en', label: 'EN' }, { value: 'hi', label: <span lang="hi">हिं</span> }]}
                className="w-[104px]"
              />
            </div>
          </nav>
        </header>

        <main key={route.name + ('id' in route ? route.id : '')} className="flex-1 animate-enter">
          {route.name === 'home' && <Home />}
          {route.name === 'job' && <Job id={route.id} />}
          {route.name === 'report' && <ReportView id={route.id} meta={meta} startAt={route.t} />}
          {route.name === 'profile' && <ProfileView id={route.id} meta={meta} />}
        </main>

        <footer className="no-print px-4 pb-8 pt-12">
          <p className="mx-auto max-w-2xl text-center text-xs leading-relaxed text-ink-3">{t.footer}</p>
        </footer>
      </div>
    </LangContext.Provider>
  )
}
