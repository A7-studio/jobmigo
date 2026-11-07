import { useEffect, useRef } from 'react'
import type { CSSProperties, ElementType, ReactNode } from 'react'

/**
 * Fades its children up when they first scroll into view. The server HTML is fully
 * visible; the hidden state is applied only after hydration, only for elements below the
 * fold and only when the visitor has not asked for reduced motion.
 */
export function Reveal({
  as: Tag = 'div',
  delay = 0,
  className,
  children,
}: {
  as?: ElementType
  /** Milliseconds to wait after entering view, for staggering siblings. */
  delay?: number
  className?: string
  children: ReactNode
}) {
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    if (el.getBoundingClientRect().top < window.innerHeight) {
      // In view already (or a re-run after hot reload): never leave it hidden.
      if (el.dataset.reveal === 'pending') el.dataset.reveal = 'in'
      return
    }

    el.dataset.reveal = 'pending'
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          el.dataset.reveal = 'in'
          observer.disconnect()
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <Tag
      ref={ref}
      className={className}
      style={{ '--reveal-delay': `${delay}ms` } as CSSProperties}
    >
      {children}
    </Tag>
  )
}
