"""CLI demo script — run with: python main.py"""

from pawpal_system import Owner, Pet, Task, Scheduler

# ── Setup ──────────────────────────────────────────────────────────────────
owner = Owner("Jordan")

mochi = Pet("Mochi", "dog")
mochi.add_task(Task("Morning walk",   time="07:30", duration_minutes=30, priority="high",   frequency="daily"))
mochi.add_task(Task("Breakfast",      time="08:00", duration_minutes=10, priority="high",   frequency="daily"))
mochi.add_task(Task("Medication",     time="08:00", duration_minutes=5,  priority="high",   frequency="daily"))  # conflict!
mochi.add_task(Task("Evening walk",   time="18:00", duration_minutes=30, priority="high",   frequency="daily"))
mochi.add_task(Task("Grooming",       time="10:00", duration_minutes=20, priority="medium", frequency="weekly"))

luna = Pet("Luna", "cat")
luna.add_task(Task("Feeding",         time="08:30", duration_minutes=5,  priority="high",   frequency="daily"))
luna.add_task(Task("Litter box",      time="09:00", duration_minutes=5,  priority="medium", frequency="daily"))
luna.add_task(Task("Playtime",        time="19:00", duration_minutes=15, priority="low",    frequency="once"))

owner.add_pet(mochi)
owner.add_pet(luna)

scheduler = Scheduler(owner)

# ── Today's schedule ───────────────────────────────────────────────────────
print("=" * 55)
print(f"  PawPal+ — Today's Schedule for {owner.name}")
print("=" * 55)

for entry in scheduler.generate_schedule():
    status = "✓" if entry["done"] else "○"
    print(
        f"  [{status}] {entry['time']}  {entry['pet']:<8}"
        f"  {entry['task']:<20}  {entry['duration']:<8}"
        f"  [{entry['priority']}]"
    )

# ── Conflict warnings ──────────────────────────────────────────────────────
print()
conflicts = scheduler.detect_conflicts()
if conflicts:
    print("⚠  Conflicts detected:")
    for w in conflicts:
        print(f"   {w}")
else:
    print("✓  No scheduling conflicts.")

# ── Mark a task complete (with recurrence) ─────────────────────────────────
print()
msg = scheduler.mark_task_complete("Mochi", "Morning walk")
print(f"→  {msg}")

# ── Filtering demos ────────────────────────────────────────────────────────
print()
print("Tasks for Mochi only:")
for t in scheduler.filter_by_pet("Mochi"):
    print(f"   {t}")

print()
print("Incomplete tasks:")
for pet, task in scheduler.filter_by_status(completed=False):
    print(f"   {pet.name}: {task}")
