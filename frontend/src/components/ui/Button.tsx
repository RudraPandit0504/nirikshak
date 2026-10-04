import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'glass' | 'ghost'
type Size = 'sm' | 'md' | 'lg'

const BASE =
  'relative inline-flex items-center justify-center gap-2 rounded-full font-semibold whitespace-nowrap select-none ' +
  'transition-[transform,background,box-shadow,opacity] duration-300 ease-[var(--ease-spring)] active:scale-[.96] ' +
  'disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[color-mix(in_oklab,var(--accent)_35%,transparent)]'

const VARIANT: Record<Variant, string> = {
  // Vivid gradient capsule with a glossy top highlight, like an iOS prominent button.
  primary:
    'text-white bg-[linear-gradient(135deg,#ff9500,#ff5e3a)] shadow-[inset_0_1px_0_rgba(255,255,255,.45),0_8px_24px_-8px_rgba(255,94,58,.65)] ' +
    'hover:shadow-[inset_0_1px_0_rgba(255,255,255,.5),0_12px_30px_-8px_rgba(255,94,58,.75)] hover:-translate-y-px',
  glass: 'glass-pill text-ink hover:bg-[var(--glass-hover)]',
  ghost: 'text-ink-2 hover:text-ink hover:bg-[var(--glass-inset)]',
}

const SIZE: Record<Size, string> = {
  sm: 'h-9 px-3.5 text-[13px]',
  md: 'h-11 px-5 text-sm',
  lg: 'h-14 px-7 text-base',
}

type Common = { variant?: Variant; size?: Size; className?: string; children?: ReactNode }

export function Button({ variant = 'glass', size = 'md', className = '', children, ...rest }: Common & ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`${BASE} ${VARIANT[variant]} ${SIZE[size]} ${className}`} {...rest}>{children}</button>
}

export function LinkButton({ variant = 'glass', size = 'md', className = '', children, ...rest }: Common & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <a className={`${BASE} ${VARIANT[variant]} ${SIZE[size]} ${className}`} {...rest}>{children}</a>
}
