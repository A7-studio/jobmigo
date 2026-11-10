import { createFileRoute } from '@tanstack/react-router'
import { JobWorkspace } from '#/components/jobs/job-workspace'

// `jobs_` keeps this a sibling of the Jobs page, which has no Outlet for a child.
export const Route = createFileRoute('/_app/jobs_/$jobId')({
  head: () => ({ meta: [{ title: 'Job | Jobmigo' }] }),
  component: Workspace,
})

function Workspace() {
  const { jobId } = Route.useParams()
  return <JobWorkspace jobId={jobId} />
}
