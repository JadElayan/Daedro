# Daedro game plan

*Written 2026-11-25. Review every Sunday. Everything below is a plan and a set of hypotheses, not results.*

## Where we are
- **Built:** a working prototype. It runs pull-request checks, video replays, a failure library and release records across robot setups. It supports your own controller and camera policies, plus the SO-101 (experimental). It's live at daedro.vercel.app and github.com/JadElayan/Daedro.
- **Not proven:** that anyone needs it. There are no users, no conversations yet, and no hardware validation.
- **The one question that matters next:** *do robotics teams struggle to decide whether a software update is safe to ship, and would they use Daedro to decide?*

## The goal for the next 6 weeks
**One real team runs Daedro on one real update they hesitated to ship, and asks to use it again on the next one.** Everything else serves that.

## Two front doors, one product
| | Builders (hobbyists, students, researchers) | Robot teams and manufacturers |
|---|---|---|
| Who does outreach | **Jad** | Jad, with drafts from Claude |
| Where they are | LeRobot Discord, Hugging Face, r/robotics, UCI labs | LinkedIn, warm intros, UCI career and alumni networks, robotics meetups |
| Their question | "Is my new policy better than my last one?" | "Which robots can take this update, and what's the evidence?" |
| What we learn | Whether the workflow and preview links are wanted; which policy formats matter | Whether release decisions are painful, and who owns them |
| Money | Late (free tier) | Sooner (paid pilots) |

## Week by week

**Week 1: start conversations (target: 20 messages sent, 5 calls booked)**
- Builders: post the PR #1 demo and video in the LeRobot community. Ask the builder question below, not "would you use this?"
- UCI: email 5 robotics labs or grad students (CLAUDE.md track 2).
- Industry: message 10 robotics engineers or release owners at manufacturing, warehouse and lab-automation companies.
- Run a free USPTO search for "Daedro". If it's clear, buy daedro.ai (and getdaedro.com).

**Week 2: calls (target: 5–8 interviews)**
- Use the interview script below. Write notes within an hour of each call, in `docs/interviews/` (one file per call, no confidential details).
- After each call, update the pain log: what they struggle with, how often, what they use today, what it costs them.

**Week 3: pick the first case**
- Choose the single team with the sharpest, most recent pain and a behaviour Daedro can actually run (or plausibly run).
- Offer a free pilot: "Give us one update you hesitated to ship. We'll hand you a release record within a week."

**Weeks 4–5: deliver the case by hand**
- Integrate their controller or policy ourselves, whatever it takes (this is the "do things that don't scale" phase).
- Deliver the release record and sit with them while they read it. Ask what they'd decide, and what's missing.

**Week 6: the gate (from CLAUDE.md)**
- Did a team use it on a real decision, and ask for it again? Then build only what that case needs next.
- If not, diagnose honestly:
  - No replies → an outreach problem, not market evidence. Change channels and messages.
  - Conversations but no shared case → an access, trust or relevance problem.
  - Cases but no repeated pain → rethink the wedge. Maybe it's commissioning new cells, not releasing updates.
  - Clear pain we can't execute → narrow the scope, or find the robotics co-founder first.

## Scripts

**Builder question** (Discord, Hugging Face, posts):
> "When you train a new version of your policy, how do you know it's actually better before you run it on the arm? What's the last time a new version made things worse?"

**Industry opener** (≤ 5 sentences):
> "I'm a UC Irvine student building Daedro, which tests robot software updates in simulation and shows which robot setups can take them. I'm not selling anything yet. I'm trying to learn how teams decide an update is safe to ship. Could I ask you 20 minutes of questions about the last update you hesitated to release? Here's a 1-page example of what we produce: daedro.vercel.app/release/"

**Interview script** (20–30 minutes, listen 80% of the time):
1. "Walk me through the last robot update you hesitated to ship. What were you unsure about?"
2. "How did you decide which machines could get it? Who made the call?"
3. "What evidence did you have: sim, bench tests, logs? Which did you actually trust?"
4. "Tell me about a failure you couldn't reproduce."
5. "What happened the last time an update went wrong? What did it cost?"
6. "What do you use today for this? What's annoying about it?"
7. Only at the end: show the release record. "What would you change? Would this have helped on that update?"
8. "Who else should I talk to?" (always ask)

Never ask "would you use/pay for this?" People say yes to be polite.

## Metrics to track (in a simple spreadsheet)
- Messages sent → replies → calls → shared cases → repeat use. Track it as a funnel; the numbers show where it leaks.
- Pain log: who, what problem, how often, current workaround, cost.
- Form sign-ups from the website (the Google Form), and which "who it's for" box they fit.

## Co-founder search (start now, in parallel)
- The gap is robotics and controls depth. Look for UCI robotics or ML grad students, people active in LeRobot or MuJoCo communities, and engineers who've shipped robots.
- The best signal: someone who has personally been burned by a bad robot release and gets excited by the release record.
- Work on one small real task together before deciding anything.

## YC
- Applications open several times a year. Check ycombinator.com/apply for the current deadline; don't rely on memory.
- What strengthens the application, in order:
  1. A team using it, ideally asking for it again.
  2. Specific interview evidence: "8 of 10 teams said X; here are their words."
  3. A co-founder with robotics depth.
  4. The working product, which you already have.
- What weakens it: a big vision with no user, invented numbers, or "it's for everyone". Never put a metric in an application that you can't show.

## What not to do (for now)
- Don't buy a Franka. Buy an SO-101 only if builder conversations show demand. It would also let us calibrate the experimental SO-101 simulation.
- Don't build dashboards, pricing tiers, hosted GPU runs or fleet deployment until a real case asks for them.
- Don't add robots or simulators speculatively; add the one the first real team uses.
- Don't describe simulation results as hardware validation, anywhere.

## Next 7 days: checklist
- [ ] USPTO search for "Daedro"; buy the domain if clear
- [ ] Post the builder question and demo in the LeRobot community (Jad)
- [ ] Email 5 UCI robotics labs or grad students
- [ ] Message 10 industry engineers or release owners
- [ ] Set up the funnel and pain-log spreadsheet
- [ ] Book at least 3 calls
- [ ] Start the co-founder list: 10 names
