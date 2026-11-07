import { Link } from '@tanstack/react-router'
import { Wordmark } from '#/components/Migo'

export function Footer({ contactEmail }: { contactEmail: string }) {
  return (
    <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-border py-8 text-sm text-muted">
      <div className="flex flex-col gap-1">
        <Wordmark />
        <span>A product of A7Studio</span>
      </div>
      <nav aria-label="Footer" className="flex flex-wrap gap-x-6">
        <Link
          to="/privacy"
          className="inline-flex min-h-11 items-center font-bold text-accent-strong hover:underline"
        >
          Privacy
        </Link>
        {contactEmail && (
          <a
            href={`mailto:${contactEmail}`}
            className="inline-flex min-h-11 items-center font-bold text-accent-strong hover:underline"
          >
            Contact
          </a>
        )}
      </nav>
    </footer>
  )
}
