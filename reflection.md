# PawPal+ Project Reflection

## System Design

Three core user actions:
1. Add a pet (with name and species).
2. Add a care task to a pet (description, time, duration, priority, frequency).
3. Generate and view a sorted daily schedule with conflict warnings.

---

## 1. System Design

**a. Initial design**

The system uses four classes:
• 'Task' - Represents one care activity. Holds description, scheduled time, duration, priority, frequency, and completion status.

• 'Pet' - Stores a pet's profile and owns a list of Task objects. Provides 'add_task' and 'remove_task'. 

• 'Owner' - Manages a list of Pet objects and exposes 'get_all_tasks()' as a flat (pet, task) pair list for the scheduler. 

• 'Scheduler' - Attached to an Owner. Sorts, filters, detects conflicts, handles recurrence, and generates a daily plan. 

**b. Design changes**

Originally, 'Scheduler' stored its own flat task list. This created a duplication problem, the same task would live in both the 'Pet' and the 'Scheduler'. The design was changed so that 'Scheduler' always reads directly from 'Owner.pets' at call time 'get_all_tasks()'. This keeps a single source of truth and ensures that newly added tasks are immediately visible without any syncing step.

A 'next_due: date' field was also added to 'Task' after realising that recurrence logic needed a concrete anchor date, not just a frequency string.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers:
• Time — tasks are sorted chronologically by hour and minute so the day flows in order.

• Priority — within the same time slot, higher-priority tasks are listed first 'high > medium > low'.

• Frequency — daily/weekly tasks automatically generate a follow-up instance when marked complete.

• Conflict detection — any two tasks sharing an exact start time trigger a warning.

Priority was chosen as the secondary sort key (over duration) because a pet owner needs to know *what matters most* at a glance, not what is fastest to finish.

**b. Tradeoffs**

The conflict detector only flags exact time matches (e.g., two tasks both at "08:00"). It does not check whether a 30-minute task at 08:00 overlaps with a task at 08:15. This is a deliberate simplification: detecting overlap requires knowing each task's duration and computing intervals, which adds complexity. For a daily pet care app where tasks are mostly sequential and short, exact-time matching catches the most common mistake (double-booking the same slot) without making the code harder to maintain.

---

## 3. AI Collaboration

**a. How AI was used**

AI was used throughout this project for:
• Design brainstorming — drafting the initial class responsibilities and the 'Scheduler.generate_schedule()' return format.

• Code generation — producing the dataclass structures and method stubs from a description of the UML.

• Test generation — suggesting edge cases (empty pet list, non-existent task name, recurring vs. once-off tasks).

• Debugging — identifying that marking a task complete inside a loop while also appending to the same list could cause issues; the fix was to append after the loop exits.


**b. Judgment and verification**

An early AI suggestion had 'Scheduler' accept a flat 'list[Task]' in its constructor instead of an 'Owner'. This was rejected because it would mean the UI layer had to manually flatten all pet tasks before passing them in, losing the per-pet context needed for conflict detection and the "filter by pet" feature. The owner-attached design was kept and the AI suggestion was overridden after tracing through what information each method actually needed.

---

## 4. Testing and Verification

**a. What was tested**

16 automated tests covering:
• 'Task.mark_complete()' — status change, 'once' returns 'None', 'daily'/'weekly' return next occurrence with correct date.

• 'Pet.add_task()' / 'remove_task()' — count changes and return values.

• 'Scheduler.sort_by_time()' — chronological order.

• 'Scheduler.filter_by_pet()' — correct tasks returned; unknown pet returns empty list.

• 'Scheduler.filter_by_status()' — only incomplete tasks in result.

• 'Scheduler.detect_conflicts()' — finds duplicate times; no false positives.

• 'Scheduler.mark_task_complete()' — recurrence appended; not-found message returned.

• 'Scheduler.generate_schedule()' — result is non-empty and has required keys.

These tests were important because the scheduling logic (sorting, recurrence, conflict detection) is the core value of the app. If any of these fail silently, the UI would show incorrect data with no visible error.

**b. Confidence**

The main gap is overlap detection. 
Edge cases to test next:
• Two pets with tasks at the same time (cross-pet conflict).
• A pet with zero tasks passed to 'generate_schedule()'.
• Time strings in invalid formats entered through the UI.

---

## 5. Reflection

**a. What went well**

The "CLI-first" workflow (building and verifying 'pawpal_system.py' through 'main.py' before touching 'app.py') made UI integration simple. Every Streamlit button already had a method to call.

**b. What I would improve**

The conflict detector would be upgraded to check for overlapping durations, not just exact time matches. I would also add a drag-to-reorder UI so owners can manually override the generated schedule order.

**c. Key takeaway**

AI tools are fastest when given precise contracts: input types, output types, and the one behaviour to implement. When the prompt is vague ("make the scheduler smart"), the output requires heavy editing. When the prompt is specific ("given a list of (Pet, Task) pairs, return them sorted by task.time as HH:MM strings"), the output is immediately usable.

---

# Module 4 Extension — Applied AI System

The Module 2 reflection above describes the original PawPal+ scheduler.
This section covers the extension built for Module 4, which adds a RAG
layer on top of the existing system.

## 6. What I extended

The original Scheduler was rule-based: sort by time, break ties with
priority, flag exact-time conflicts. That logic stays intact. On top of
it I built:

- A 13-document pet-care knowledge base (`knowledge/*.md`).
- A retrieval pipeline using local sentence-transformer embeddings and
  cosine top-k search.
- A grounded generator using Gemini 2.0 Flash with a system prompt that
  forbids hallucination and medical diagnosis.
- A confidence scorer derived from retrieval similarity.
- Two new user-facing features: free-form pet-care Q&A ("Ask PawPal")
  and AI-explained schedules ("Explain this schedule" button).
- An evaluation suite with 10 golden Q&A pairs and a retrieval accuracy
  threshold (currently 100%, threshold set at 80%).
- Structured JSONL logging of every RAG call (question, retrieval
  scores, latency, errors).

Every new piece sits in a `rag/` package so the UI and backend
scheduler can be swapped without touching the AI layer.

## 7. Design decisions in the extension

**Why RAG instead of a fine-tuned model.** A 4,500-word knowledge base
doesn't justify training. RAG keeps the knowledge editable as plain
markdown — adding a new section is a git commit, not a retraining run.

**Why local embeddings + cloud LLM.** Local embeddings (~80MB,
`all-MiniLM-L6-v2`) cost nothing and require no API key, which keeps
setup friction low for graders and any future portfolio reviewers.
Cloud generation via Gemini 2.0 Flash gives near-instant quality on a
free tier — better than running a small local LLM that would either be
slow or low-quality.

**Why retrieval similarity for confidence rather than self-rating.**
The LLM is constrained by my prompt to ground its answer in the
retrieved chunks. So a weak retrieval is a weak answer regardless of
how fluent the prose sounds. Asking the LLM to rate its own answer
would just measure its writing style.

**Why markdown-aware chunking instead of fixed character windows.**
Markdown documents have meaningful section breaks (`## headers`). A
fixed-window split would shred those boundaries and dilute embedding
quality. Splitting on `##` and including the section header in the
embedding text gave better retrieval on my golden set.

## 8. Limitations and biases

- **One author, one perspective.** I curated the knowledge base myself.
  A vet, a breed specialist, and a behaviorist would all flag nuance I
  miss.
- **Western, single-household assumptions.** "Two walks a day" assumes
  someone is home or has a yard. Shift workers, apartment dwellers, and
  pet owners in different climates need different defaults that the
  system doesn't adapt to.
- **English-only generation.** The embedder supports many languages,
  but the system prompt and knowledge base are English, so non-English
  questions lose grounding fidelity.
- **No feedback loop.** Users can't flag bad answers. A future version
  would log thumbs-up/down and surface low-quality chunks.

## 9. Could this AI be misused?

The most realistic misuse is treating PawPal+ as a vet substitute —
ignoring a sick pet because the chatbot sounded confident. Mitigations
in place:

1. The system prompt forbids medical diagnoses and always recommends
   vet consultation for health concerns.
2. The confidence badge surfaces uncertainty visually.
3. The README and UI consistently frame the tool as a planner, not a
   medical resource.
4. The `health_signs.md` document and the system prompt both end with
   explicit "see a vet" language.

A determined misuser can still ignore these. That is a real limit of
any informational AI.

## 10. What surprised me while testing

**Chunk metadata mattered more than expected.** My first version
embedded only chunk bodies. Queries like "How often should I brush a
Maine Coon?" kept matching general dog-grooming chunks because cat
breed names didn't appear in the bodies. Once I prepended
`title — section` to each chunk's embedding text, the right chunks
surfaced. I'd read about this in RAG papers but didn't internalize it
until it broke on real queries.

**The LLM sounds confident even when retrieval is weak.** Without the
explicit confidence score, a user would have no way to tell. Adding
the badge changed how trustworthy the system *feels* in a way I didn't
predict — it makes the system more honest, even though the underlying
generation didn't change.

**Out-of-scope refusal worked first try.** When I tested "What's the
best stock to invest in?", retrieval similarity stayed below 0.2 and
the LLM correctly said "I don't know — ask a financial advisor." I'd
worried I'd need to add a separate classifier for out-of-scope
questions; the retrieval-similarity signal turned out to be enough.

## 11. AI collaboration during the extension

I worked with an AI assistant throughout, treating it as a thinking
partner rather than an author. I supplied the design constraints, it
sketched options, and I picked and rewrote.

**One helpful suggestion.** When I asked about confidence scoring, the
assistant suggested deriving it from retrieval similarity instead of
asking the LLM to self-rate. The reasoning — "the LLM is grounded by
your prompt, so retrieval IS the quality signal" — was the right
abstraction and shaped the entire `confidence.py` module.

**One flawed suggestion.** Early on I asked it to draft the chunking
strategy. The first proposal was a fixed character window with
overlap. I rejected this because the markdown docs already have
meaningful section breaks (`##` headers), and a character-window split
would shred those boundaries. I implemented markdown-aware chunking
instead, which gave noticeably better retrieval accuracy on the golden
set.

## 12. Key takeaway from the extension

Building an AI system is mostly about **building boring scaffolding
around a small AI core**: input validation, prompt templates, error
handling, citations, logging, evaluation. The actual LLM call is one
function. Everything else is what makes it usable, debuggable, and
trustworthy. A real applied AI engineer spends 10% of their time on
the model and 90% on everything around it.
