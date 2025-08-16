## QA Evaluation Score and Metrics

This document explains, at an executive level, how the platform evaluates call quality and which metrics we compute. The goal is to provide a clear, consistent view of agent performance and customer experience for coaching, quality assurance, and operational dashboards.

---

## What We Produce

- **QA Evaluation Score (0–100)**: A holistic score of the agent’s performance on a call.
- **Operational Metrics**: Objective indicators derived from the transcript (e.g., clarity, speaking rate, talk-time balance, sentiment).
- **Actionable Insights**: Targeted suggestions and evidence (snippets) for coaching.

---

## How the QA Evaluation Score Is Calculated

We combine an AI rubric review with a robust baseline heuristic so the score is reliable even when AI output is incomplete.

- **Primary method (AI rubric, 0–100)**
  - The model reviews the transcript and scores the agent across five criteria, each 0–20 points:
    1) Professionalism & Tone
    2) Active Listening & Empathy
    3) Problem Diagnosis & Resolution Accuracy
    4) Policy/Process Adherence
    5) Communication Clarity & Structure
  - The five criterion scores are summed into the **overall QA Evaluation Score (0–100)**.
  - The model also returns supporting evidence (verbatim snippets), a speaker mapping, and suggested improvements.

- **Fallback method (baseline heuristic, 0–100)**
  - When the AI score is missing or invalid, we compute a score directly from transcript-derived metrics:
    - Start at 50 points (baseline).
    - **Clarity**: +0 to +20 based on transcription confidence.
    - **Sentiment**: +5 (negative), +10 (neutral), +15 (positive).
    - **Speaking rate**: +10 if optimal (120–180 wpm), +5 if acceptable (100–200 wpm), otherwise 0.
    - **Talk-time balance**: up to +5 based on how balanced the agent and customer speaking times are.
  - The result is clipped to the 0–100 range.

- **Which score we use**
  - We prefer the AI rubric score when present.
  - If the AI score is absent, we use the baseline heuristic score.

---

## Operational Metrics (What We Track)

All metrics are computed from the transcript and its segments, and are exposed to the app and dashboards.

- **Clarity**
  - What it is: Proxy for audio/transcript quality derived from provider confidence.
  - How it’s computed: Provider confidence scaled to 0–100.
  - Why it matters: Higher clarity improves understanding and reduces miscommunication.

- **Speaking Rate (words per minute)**
  - What it is: Pace of the conversation.
  - How it’s computed: `(word_count / duration_seconds) * 60`.
  - Why it matters: Too fast or too slow can reduce comprehension and customer satisfaction.

- **Talk-Time by Role**
  - What it is: Seconds spoken by Agent vs Customer.
  - How it’s computed: Sum of segment durations attributed to each speaker.
  - Why it matters: Balance indicates collaboration; over‑talking can signal poor experience.

- **Silence Duration**
  - What it is: Total non-speaking time during the call.
  - How it’s computed: `call_duration − (agent_talk_time + customer_talk_time)`.
  - Why it matters: Excessive silence can indicate friction (e.g., long holds, searching for answers).

- **Sentiment (Overall)**
  - What it is: Aggregate emotional tone across the call.
  - How it’s computed: Duration‑weighted average of segment sentiments, mapped to Positive / Neutral / Negative.
  - Why it matters: A strong indicator of customer experience and resolution quality.

- **Sentiment by Speaker**
  - What it is: Agent and Customer sentiments separately.
  - How it’s computed: Same duration‑weighted approach, filtered by speaker.
  - Why it matters: Separates agent tone from customer mood—useful for coaching.

- **Word Count**
  - What it is: Total words in the transcript.
  - How it’s computed: Provided by the transcription service.
  - Why it matters: Context for speaking rate and talk-time analysis.

---

## Data Sources and Timing

- **Transcription & Segments**: Provided by our transcription provider (e.g., AssemblyAI), including per‑segment timing, speaker labels, and confidence.
- **AI QA Review**: Performed by our AI model on the final transcript using a strict rubric and JSON output contract.
- **When We Compute**: After the transcript is completed (via webhook or polling). Metrics are computed first; the AI QA review then runs using the transcript and metrics. If the AI output lacks a valid score, we fall back to the baseline heuristic.

---

## How to Interpret the QA Evaluation Score

- **Scale**: 0–100; higher is better.
- **Composition**: Prefer AI rubric (five 0–20 criteria) with evidence; otherwise baseline heuristic from clarity, sentiment, speaking rate, and talk‑time balance.
- **Use Cases**: Coaching (drill into criteria and insights), trend analysis (per agent/team), and operations (monitoring quality at scale).

---

## Field Names (for Integrations)

Where applicable, API responses use camelCase fields.

- Metrics: `wordCount`, `speakingRateWpm`, `clarity`, `overallScore`, `agentTalkTimeSec`, `customerTalkTimeSec`, `silenceDurationSec`, `sentimentOverall`, `sentimentBySpeaker`.
- QA Evaluation payload: `overall_score`, `criteria` (with `name`, `score`, `justification`, `supporting_segments`), `insights` (with `segment`, `explanation`, `improved_response_example`), `speaker_mapping`, `agent_label`, `customer_behavior`, and `raw_response`.

---

## Transparency and Considerations

- **Speaker inference**: If explicit speaker roles are absent, the AI infers which party is the agent and maps segments accordingly.
- **Evidence‑based**: Insights and scores include verbatim snippets for review.
- **Fallbacks for resilience**: If AI output is incomplete, the heuristic keeps the score consistent and available.
- **Not a replacement for policy**: Scores guide coaching; they do not supersede compliance rules or business policies.

---

## Summary

- We deliver a reliable **QA Evaluation Score (0–100)**, powered by an AI rubric and backed by a baseline heuristic.
- We compute **objective operational metrics** to explain and contextualize the score.
- Leaders get a consistent, evidence‑based view of call quality for coaching and performance management.
