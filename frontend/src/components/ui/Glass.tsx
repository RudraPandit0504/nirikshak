import type { ElementType, HTMLAttributes, ReactNode } from 'react'

type Tone = 'none' | 'red' | 'amber' | 'green'

const TONE: Record<Tone, string> = {
  none: '',
  red: 'bg-[color-mix(in_oklab,#ff3b30_10%,var(--glass))]',
  amber: 'bg-[color-mix(in_oklab,#ff9f0a_12%,var(--glass))]',
  green: 'bg-[color-mix(in_oklab,#34c759_12%,var(--glass))]',
}

/** A frosted-glass surface. `strong` is more opaque, for primary panels and text-heavy content. */
export default function Glass({
  as: Tag = 'div', strong = false, tone = 'none', className = '', children, ...rest
}: { as?: ElementType; strong?: boolean; tone?: Tone; className?: string; children?: ReactNode } & HTMLAttributes<HTMLElement>) {
  return (
    <Tag className={`${strong ? 'glass-strong' : 'glass'} ${TONE[tone]} ${className}`} {...rest}>
      {children}
    </Tag>
  )
}
