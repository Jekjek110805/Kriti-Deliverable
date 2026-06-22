# Cost Discipline Checklist

## Before Running Any Operation

Ask these questions:

### 1. What type of task is this?

- [ ] General advice / brainstorming / learning → **Use FREE model**
- [ ] Architecture thinking / prompt drafting → **Use FREE model**
- [ ] Testing a workflow → **Use STANDARD model on ONE SAMPLE first**
- [ ] Draft output / internal tool → **Use STANDARD model**
- [ ] Processing real client data → **Use STANDARD model**
- [ ] Final production report → **Use PREMIUM model**
- [ ] Client-facing output → **Use PREMIUM model**

### 2. Can I test on a small sample first?

- [ ] Yes → Run on 1-2 items first with STANDARD
- [ ] No, this is already a single item → Proceed
- [ ] No, this is a full workflow → Test with 1 sample, then run full

### 3. Is this draft or final quality?

- [ ] Draft → **STANDARD is fine**
- [ ] Final → **PREMIUM required**

### 4. Does this involve real client/project data?

- [ ] No, test/mock data → **STANDARD is fine**
- [ ] Yes, real data → **STANDARD minimum, PREMIUM for final**

### 5. Am I about to use an expensive model?

- [ ] Yes → Can FREE do this instead?
- [ ] Yes → Can STANDARD do this instead?
- [ ] No, PREMIUM is justified → Proceed

## Cost Reference

| Model Tier | Cost per 1K tokens | When to use |
|------------|-------------------|-------------|
| Free/Cheap | $0.00 | Advice, brainstorming, learning |
| Standard | $0.002 | Testing, drafts, samples |
| Premium | $0.030 | Final output, client data |

## The Golden Rule

**"Choose the cheapest model that is good enough for the task."**

Not "always use the best."
Not "always use Hermes."
Not "always use free."

**Right tool for the right job.**

## Platform Enforcement

The platform helps enforce this:

1. `/api/models/check` — Validates your model selection before running
2. `/api/models/tiers` — Shows what each tier should be used for
3. `/api/models/usage` — Tracks actual spending
4. Each API endpoint has a recommended tier

## Examples

| Task | Wrong Choice | Right Choice | Why |
|------|-------------|-------------|-----|
| "What should I do next?" | Premium | Free | General advice |
| Brainstorm content ideas | Premium | Free/Standard | Not production |
| Test opportunity finder on 1 row | Premium | Standard | Testing phase |
| Generate final Monthly Report | Standard | Premium | Client-facing |
| Process real GSC data | Free | Standard | Real data |
| Write production blog post | Standard | Premium | Final output |
