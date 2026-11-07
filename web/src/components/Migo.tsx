export function Migo({
  size = 48,
  label,
  className = '',
  joy = false,
}: {
  size?: number
  /** Accessible name; omit when the mascot is decorative. */
  label?: string
  className?: string
  /** Open-mouth smile with sparkles, for welcome moments. */
  joy?: boolean
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      className={`migo ${className}`}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path
        d="M17 15v-3.5A3.5 3.5 0 0 1 20.5 8h7a3.5 3.5 0 0 1 3.5 3.5V15"
        fill="none"
        stroke="#1A1A18"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <rect x="5" y="14" width="38" height="29" rx="10" fill="#D97757" />
      <g className="migo-eyes">
        <circle cx="17.5" cy="26" r="4.2" fill="#fff" />
        <circle cx="30.5" cy="26" r="4.2" fill="#fff" />
        <circle cx="18.3" cy="26.4" r="2" fill="#1A1A18" />
        <circle cx="31.3" cy="26.4" r="2" fill="#1A1A18" />
      </g>
      {joy ? (
        <>
          <path d="M18.5 33.5q5.5 9 11 0z" fill="#1A1A18" />
          <path
            d="M21.5 36.6q2.5 2 5 0"
            fill="none"
            stroke="#F1CBBA"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
          <path
            d="M42 7l1.2 2.6 2.6 1.2-2.6 1.2L42 14.6l-1.2-2.6-2.6-1.2 2.6-1.2zM5 4l.9 1.9 1.9.9-1.9.9L5 9.6l-.9-1.9-1.9-.9 1.9-.9z"
            fill="#D97757"
          />
        </>
      ) : (
        <path
          d="M19.5 34.5q4.5 4 9 0"
          fill="none"
          stroke="#1A1A18"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
      )}
      <circle cx="11.5" cy="32" r="2.3" fill="#F1CBBA" opacity=".8" />
      <circle cx="36.5" cy="32" r="2.3" fill="#F1CBBA" opacity=".8" />
    </svg>
  )
}

export function Wordmark({ className = '' }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-2 font-display text-2xl font-bold text-ink ${className}`}
    >
      <Migo size={36} />
      <span>
        job<span className="text-accent-strong">migo</span>
      </span>
    </span>
  )
}
