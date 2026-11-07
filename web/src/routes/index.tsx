import { createFileRoute } from '@tanstack/react-router'
import { AiSteps } from '#/components/home/AiSteps'
import { Footer } from '#/components/home/Footer'
import { Honest } from '#/components/home/Honest'
import { Hero } from '#/components/home/Hero'
import { HowItWorks } from '#/components/home/HowItWorks'
import { Journey } from '#/components/home/Journey'
import { Nav } from '#/components/home/Nav'
import { Waitlist } from '#/components/home/Waitlist'
import {
  Discover,
  Evaluate,
  GetSeen,
  Prepare,
  StayInMotion,
} from '#/components/home/Sections'
import { getSiteConfig } from '#/lib/site.functions'

const TITLE = 'Jobmigo: apply to the right jobs with a CV that fits'
const DESCRIPTION =
  'Jobmigo is an AI job-application assistant being built to help you check whether jobs are really open, fit your CV to them honestly, and apply with confidence. It does not guarantee interviews or jobs. Join the early-access waitlist.'

export const Route = createFileRoute('/')({
  loader: () => getSiteConfig(),
  head: ({ loaderData }) => {
    const url = loaderData?.publicUrl ?? ''
    const image = `${url}/og.png`
    return {
      meta: [
        { title: TITLE },
        { name: 'description', content: DESCRIPTION },
        { property: 'og:type', content: 'website' },
        { property: 'og:site_name', content: 'Jobmigo' },
        { property: 'og:title', content: TITLE },
        { property: 'og:description', content: DESCRIPTION },
        { property: 'og:url', content: url },
        { property: 'og:image', content: image },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:title', content: TITLE },
        { name: 'twitter:description', content: DESCRIPTION },
        { name: 'twitter:image', content: image },
      ],
      links: [
        { rel: 'canonical', href: url },
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
      ],
    }
  },
  component: Home,
})

function Home() {
  const { contactEmail } = Route.useLoaderData()
  return (
    <div id="top" className="mx-auto max-w-[1200px] px-4 sm:px-6">
      <Nav />
      <main>
        <Hero />
        <Journey />
        <AiSteps />
        <Discover />
        <Evaluate />
        <Prepare />
        <GetSeen />
        <StayInMotion />
        <HowItWorks />
        <Honest />
        <Waitlist />
      </main>
      <Footer contactEmail={contactEmail} />
    </div>
  )
}
