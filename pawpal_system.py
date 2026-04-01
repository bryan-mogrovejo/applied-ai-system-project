"""PawPal+ backend logic: Owner, Pet, Task, and Scheduler classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A single pet care activity."""

    description: str
    time: str  # "HH:MM" 24-hour format
    duration_minutes: int
    priority: str = "medium"  # "low" | "medium" | "high"
    frequency: str = "once"   # "once" | "daily" | "weekly"
    completed: bool = False
    next_due: date = field(default_factory=date.today)

    def mark_complete(self) -> Optional["Task"]:
        """Mark this task complete and return a follow-up task if recurring."""
        self.completed = True
        if self.frequency == "daily":
            return Task(
                description=self.description,
                time=self.time,
                duration_minutes=self.duration_minutes,
                priority=self.priority,
                frequency=self.frequency,
                next_due=self.next_due + timedelta(days=1),
            )
        if self.frequency == "weekly":
            return Task(
                description=self.description,
                time=self.time,
                duration_minutes=self.duration_minutes,
                priority=self.priority,
                frequency=self.frequency,
                next_due=self.next_due + timedelta(weeks=1),
            )
        return None

    def __str__(self) -> str:
        status = "✓" if self.completed else "○"
        return (
            f"[{status}] {self.time} — {self.description} "
            f"({self.duration_minutes} min, {self.priority} priority)"
        )


# ---------------------------------------------------------------------------
# Pet
# ---------------------------------------------------------------------------

@dataclass
class Pet:
    """A pet belonging to an owner."""

    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task to this pet."""
        self.tasks.append(task)

    def remove_task(self, description: str) -> bool:
        """Remove a task by description. Returns True if removed."""
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.description != description]
        return len(self.tasks) < before

    def __str__(self) -> str:
        return f"{self.name} ({self.species})"


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------

class Owner:
    """A pet owner who manages one or more pets."""

    def __init__(self, name: str) -> None:
        """Initialize owner with a name and empty pet list."""
        self.name = name
        self.pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to the owner's care list."""
        self.pets.append(pet)

    def get_all_tasks(self) -> list[tuple[Pet, Task]]:
        """Return all (pet, task) pairs across every pet."""
        return [(pet, task) for pet in self.pets for task in pet.tasks]

    def __str__(self) -> str:
        return f"Owner: {self.name} ({len(self.pets)} pet(s))"


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    """The brain that organises and manages tasks across all pets."""

    PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

    def __init__(self, owner: Owner) -> None:
        """Attach the scheduler to an owner."""
        self.owner = owner

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    def sort_by_time(self) -> list[tuple[Pet, Task]]:
        """Return all tasks sorted chronologically by HH:MM time."""
        pairs = self.owner.get_all_tasks()
        return sorted(pairs, key=lambda pt: pt[1].time)

    def filter_by_pet(self, pet_name: str) -> list[Task]:
        """Return tasks belonging to a specific pet (case-insensitive)."""
        for pet in self.owner.pets:
            if pet.name.lower() == pet_name.lower():
                return list(pet.tasks)
        return []

    def filter_by_status(self, completed: bool) -> list[tuple[Pet, Task]]:
        """Return tasks filtered by completion status."""
        return [(pet, task) for pet, task in self.owner.get_all_tasks()
                if task.completed == completed]

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def detect_conflicts(self) -> list[str]:
        """Return warning strings for tasks scheduled at the same time."""
        seen: dict[str, str] = {}   # time -> "pet – description"
        warnings: list[str] = []
        for pet, task in self.owner.get_all_tasks():
            label = f"{pet.name} – {task.description}"
            if task.time in seen:
                warnings.append(
                    f"Conflict at {task.time}: '{seen[task.time]}' "
                    f"and '{label}'"
                )
            else:
                seen[task.time] = label
        return warnings

    # ------------------------------------------------------------------
    # Task completion with recurrence
    # ------------------------------------------------------------------

    def mark_task_complete(self, pet_name: str, description: str) -> str:
        """Mark a task complete and schedule the next occurrence if recurring."""
        for pet in self.owner.pets:
            if pet.name.lower() != pet_name.lower():
                continue
            for task in pet.tasks:
                if task.description.lower() == description.lower() and not task.completed:
                    next_task = task.mark_complete()
                    if next_task:
                        pet.add_task(next_task)
                        return (
                            f"'{description}' marked complete. "
                            f"Next occurrence added for {next_task.next_due}."
                        )
                    return f"'{description}' marked complete."
        return f"Task '{description}' not found for pet '{pet_name}'."

    # ------------------------------------------------------------------
    # Schedule generation
    # ------------------------------------------------------------------

    def generate_schedule(self) -> list[dict]:
        """
        Build a daily plan sorted by time, then by priority within the same slot.
        Returns a list of dicts ready for display.
        """
        pairs = self.sort_by_time()
        # Secondary sort: priority within same time slot
        pairs.sort(key=lambda pt: (pt[1].time, self.PRIORITY_ORDER.get(pt[1].priority, 1)))

        schedule = []
        for pet, task in pairs:
            schedule.append({
                "time": task.time,
                "pet": pet.name,
                "task": task.description,
                "duration": f"{task.duration_minutes} min",
                "priority": task.priority,
                "frequency": task.frequency,
                "done": task.completed,
            })
        return schedule
