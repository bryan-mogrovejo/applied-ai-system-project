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
