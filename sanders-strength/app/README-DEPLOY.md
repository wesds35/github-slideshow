# Deploying Sanders Strength for Real Athletes

This walks through going from "runs on my machine" to "a URL my athletes can log into on their own
phones, each seeing only their own data." Everything here is free at small-roster scale.

Total time: ~20 minutes, most of it waiting for a project to spin up.

## 1. Create your Supabase project

1. Go to [supabase.com](https://supabase.com) → sign up (free, no card required) → **New Project**.
2. Pick any name/region and a database password (save it somewhere — you won't need it day to
   day, Supabase manages the connection for you).
3. Wait ~2 minutes for provisioning.

## 2. Run the schema

1. In your new project, open **SQL Editor** → **New query**.
2. Paste the entire contents of [`supabase/schema.sql`](./supabase/schema.sql) and click **Run**.
3. You should see "Success. No rows returned." This created every table, the row-level security
   policies that keep athletes walled off from each other, and seeded the badge tiers.

## 3. Get your project's API keys

Project **Settings → API**. You need two values:
- **Project URL** (e.g. `https://abcdefgh.supabase.co`)
- **anon public** key (a long string — this one is safe to ship in a public frontend; RLS is what
  actually protects the data, not keeping this key secret)

## 4. Configure locally and test

```
cd sanders-strength/app
cp .env.example .env.local
# paste your Project URL and anon key into .env.local
npm install
npm run dev
```

Open the printed URL. You'll land on the login screen — there's no data yet, so:

1. Click **Create your account** and sign up with your own email (this will become your coach
   account).
2. Check Supabase's default: **Authentication → Providers → Email** has "Confirm email" on by
   default, meaning you'll need to click a confirmation link before you can log in. For local
   testing you can turn this off (Authentication → Providers → Email → toggle **Confirm email**
   off) to skip that step; turn it back on before real athletes sign up, or leave it off if you'd
   rather they get in immediately — your call, both are fine for a small roster.

## 5. Promote yourself to coach

Every new signup defaults to the `athlete` role. Make your own account the coach, once, via SQL
Editor:

```sql
update public.profiles
set role = 'coach'
where id = (select id from auth.users where email = 'you@example.com');
```

Replace the email, run it, then reload the app and log in again — you'll land on the coach
dashboard instead of the "not on a roster yet" screen.

## 6. Add your athletes

From the coach dashboard, **+ Add Athlete** — name and email. This creates their roster slot but
no login yet. Send them the app's URL and tell them to sign up with that exact email; the moment
they do, their account auto-links to the slot you created and they see their own dashboard —
never anyone else's, and never your program-authoring view.

## 7. Deploy it publicly (Vercel)

1. Push this repo to GitHub if it isn't already.
2. At [vercel.com](https://vercel.com), **New Project** → import the repo.
3. Set **Root Directory** to `sanders-strength/app` (Vercel auto-detects Vite otherwise; this just
   points it at the right subfolder since the repo has other things in it).
4. Under **Environment Variables**, add `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` with the
   same values from step 3.
5. Deploy. You'll get a `*.vercel.app` URL.

Netlify works the same way (root directory setting, same two env vars, build command
`npm run build`, publish directory `dist`) if you'd rather use that.

## 8. Point Supabase at your real domain

Back in Supabase, **Authentication → URL Configuration**:
- **Site URL**: your Vercel URL (e.g. `https://sanders-strength.vercel.app`)

This is what confirmation-email links redirect back to, so athletes land on the real app instead
of `localhost`.

## What's next (not required to launch)

- **Live updates without a manual refresh**: right now the coach dashboard and scheduler refetch
  on load and after your own actions, but won't notice a different athlete's phone logging a set
  in real time. Supabase's Realtime channels (`supabase.channel(...).on('postgres_changes', ...)`)
  can push those updates in; not wired up in v1 to keep the initial migration scoped.
- **Custom domain**: Vercel supports adding your own domain for free once deployed.
- **Coach-configurable badge thresholds**: the SQL migration seeds the default tiers from
  `REFERENCE.md`; you can already edit `threshold` values directly in the `badge_definitions`
  table via Supabase's Table Editor if you want different milestones for a youth vs. collegiate
  roster.
