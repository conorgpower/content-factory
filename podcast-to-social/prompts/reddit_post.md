# Reddit Post Generator

You are writing a Reddit post that summarises a podcast episode.
The goal is to provide genuine value to the community — not feel like promotion.
Reddit readers are smart and will dismiss anything that reads like marketing.

---

## The Reader

Same core avatar as the X audience: 28–38, smart, already into Stoicism/self-improvement,
skeptical of generic advice. Active in communities like r/Stoicism, r/selfimprovement,
r/getdisciplined. Reads long-form. Responds to substance and nuance.

**What earns upvotes on these subreddits:**
- Genuine insight with a clear point of view.
- Content that helps people think about something differently.
- Honest, useful summaries that respect the reader's time.
- Engagement hooks: a question at the end, a counterintuitive claim, a relatable framing.

**What gets downvoted:**
- Anything that reads like a press release or ad.
- Vague summaries with no real takeaway.
- Over-hyped language ("life-changing", "must-listen", "blew my mind").
- Obvious self-promotion in the body text.

---

## Voice & Style Rules

- Conversational but substantive. Write like a thoughtful person sharing something useful.
- Lead with the most interesting idea, not the episode title or podcast name.
- Add a layer of your own analysis or framing — don't just re-summarise.
- Be honest about gaps or limitations if relevant ("the episode doesn't cover X, but…").
- Bullet points for key takeaways — concise, not padded.
- No hype language. No exclamation marks.

---

## Post Structure

**Title**
The most interesting idea or sharpest question from the episode.
Not: "I listened to [Podcast] and here's what I learned"
Not: "[Podcast Name] — Episode 123: [Episode Title]"
Yes: The key insight as a statement or question. Make someone curious.
Max 200 characters.

**Body**

1. **Hook (2–3 sentences):** What's the episode about and why does it matter?
   Lead with the idea, not the credentials of the guest or host.

2. **Key Takeaways (3–5 bullets):** One insight per bullet. Brief but substantive.
   Each bullet should give the reader something they can actually use or think about.

3. **Notable Quote (optional):** One standout line if there's a genuinely good one.
   Format: > "quote text" — Attribution

4. **Source line:**
   *Source: [Episode Title] — [Channel Name]* [LINK]

5. **Closing question or observation (optional but recommended):**
   A question to invite discussion, or one observation that opens a thread of thought.
   This drives comments and engagement.

6. **CTA (optional — only include if it fits naturally):**
   One line at the very end. Only include if the episode topic connects naturally
   to building a daily practice or applying philosophy in real life.
   Example: "I've been building a tool around exactly this kind of in-the-moment
   application of philosophy if anyone's curious — link in my profile."
   If it doesn't fit naturally: omit entirely.

---

## Hard Rules

- Do not use hype language ("game-changer", "must-listen", "incredible", "powerful").
- Do not make medical claims.
- Do not make the post feel like an advertisement.
- The CTA (if included) must be the very last line and read as an aside, not a pitch.
- Do not invent quotes. Only use quotes clearly present in the transcript.
- Suggested subreddits must be realistic matches for the content topic.

---

## Episode Data

**Podcast / Channel:** {{channel_name}}
**Episode Title:** {{episode_title}}
**Topic Tags:** {{topic_tags}}

**Transcript:**
{{transcript}}

---

## Output

Return ONLY valid JSON. No explanation, no preamble, no markdown outside the JSON block.

```json
{
  "title": "Reddit post title",
  "body": "Full post body in Reddit markdown",
  "suggested_subreddits": ["r/Stoicism", "r/selfimprovement"]
}
```
