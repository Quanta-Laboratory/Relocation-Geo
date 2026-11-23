/**
 * On-time scheduler for the repo's GitHub Actions.
 *
 * Why: GitHub's own `schedule:` cron starts jobs 5–8 hours late on this repo
 * (observed Nov 2026), so "daily at 21:00" digests arrived at 3 a.m. Cloudflare
 * Cron Triggers fire on the minute. Once every 30 minutes this Worker checks
 * which jobs are due in the current slot and asks GitHub to run them now
 * (workflow_dispatch), which GitHub executes within a minute or two.
 *
 * The GitHub `schedule:` entries stay in place as a fallback. Each workflow has
 * a `guard` job that skips a scheduled run if the job was already dispatched in
 * the last 12 hours, so nothing runs twice.
 *
 * Secret (set in the Cloudflare dashboard, never committed):
 *   GH_DISPATCH_TOKEN — fine-grained PAT, repo Quanta-Laboratory/Relocation-Geo,
 *   Actions: Read and write. Nothing else.
 *
 * To change the schedule edit JOBS below — times are UTC, Tbilisi = UTC+4.
 * wrangler.jsonc needs only the single "0,30 * * * *" trigger.
 */

const REPO = "Quanta-Laboratory/Relocation-Geo";
const REF = "main";

type Job = {
  workflow: string; // file name in .github/workflows
  hour: number; // UTC
  minute: 0 | 30; // must match a cron slot
  weekday?: number; // 0 = Sunday … 6 = Saturday; omit for daily
  inputs?: Record<string, string>;
};

// Mirrors the `schedule:` crons in .github/workflows/*.yml.
export const JOBS: Job[] = [
  { workflow: "daily-checked.yml", hour: 5, minute: 0 }, // 09:00 TBS
  { workflow: "deploy.yml", hour: 5, minute: 30 }, // 09:30 TBS
  { workflow: "daily-analytics-telegram.yml", hour: 6, minute: 0 }, // 10:00 TBS
  { workflow: "parliament.yml", hour: 7, minute: 0 }, // 11:00 TBS
  { workflow: "monitor.yml", hour: 8, minute: 0 }, // 12:00 TBS
  { workflow: "redaction.yml", hour: 9, minute: 0, weekday: 1 }, // Mon 13:00 TBS
  { workflow: "monitor.yml", hour: 16, minute: 0 }, // 20:00 TBS
  { workflow: "digest.yml", hour: 17, minute: 0, inputs: { mode: "scheduled" } }, // 21:00 TBS
];

export function dueJobs(at: Date): Job[] {
  // Round to the 30-minute slot this invocation belongs to (cron can fire a
  // few seconds late, never early).
  const h = at.getUTCHours();
  const m = at.getUTCMinutes() < 30 ? 0 : 30;
  const d = at.getUTCDay();
  return JOBS.filter(
    (j) => j.hour === h && j.minute === m && (j.weekday === undefined || j.weekday === d),
  );
}

async function dispatch(job: Job, token: string): Promise<void> {
  const url = `https://api.github.com/repos/${REPO}/actions/workflows/${job.workflow}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      accept: "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "relocation-ge-scheduler",
      "content-type": "application/json",
    },
    body: JSON.stringify({ ref: REF, ...(job.inputs ? { inputs: job.inputs } : {}) }),
  });
  if (res.status !== 204) {
    // Log status only — never the token. The GitHub `schedule:` fallback will
    // still run the job (late), so a failure here degrades, not breaks.
    throw new Error(`dispatch ${job.workflow} → HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
}

export async function runScheduled(scheduledTime: number, token: string | undefined): Promise<void> {
  const jobs = dueJobs(new Date(scheduledTime));
  if (!jobs.length) return;
  if (!token) {
    console.error("scheduler: GH_DISPATCH_TOKEN is not set; skipping", jobs.map((j) => j.workflow));
    return;
  }
  const results = await Promise.allSettled(jobs.map((j) => dispatch(j, token)));
  results.forEach((r, i) => {
    if (r.status === "fulfilled") console.log(`scheduler: dispatched ${jobs[i].workflow}`);
    else console.error(`scheduler: ${r.reason}`);
  });
}
