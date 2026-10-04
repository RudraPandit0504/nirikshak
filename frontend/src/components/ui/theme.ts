import { useEffect, useState } from 'react'

export type ThemePref = 'system' | 'light' | 'dark'

function apply(pref: ThemePref) {
  const dark = pref === 'dark' || (pref === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
}

/** Light / dark / follow-system theme, remembered per browser. */
export function useTheme(): [ThemePref, (p: ThemePref) => void] {
  const [pref, setPref] = useState<ThemePref>(() => {
    try {
      const v = localStorage.getItem('nirikshak-theme')
      if (v === 'light' || v === 'dark' || v === 'system') return v
    } catch {
      /* storage unavailable */
    }
    return 'system'
  })
  useEffect(() => {
    apply(pref)
    try {
      localStorage.setItem('nirikshak-theme', pref)
    } catch {
      /* ignore */
    }
    if (pref !== 'system') return
    const mq = matchMedia('(prefers-color-scheme: dark)')
    const on = () => apply('system')
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [pref])
  return [pref, setPref]
}
