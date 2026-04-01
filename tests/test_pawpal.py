"""Automated tests for PawPal+ scheduling system."""

import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pawpal_system import Owner, Pet, Task, Scheduler


# ── Fixtures ────────────────────────────────────────────────────────────────

def make_scheduler():
    owner = Owner("TestOwner")
    dog = Pet("Rex", "dog")
    dog.add_task(Task("Walk",    time="08:00", duration_minutes=30, priority="high",   frequency="daily"))
    dog.add_task(Task("Feed",    time="07:00", duration_minutes=10, priority="high",   frequency="daily"))
    dog.add_task(Task("Groom",   time="10:00", duration_minutes=20, priority="medium", frequency="weekly"))
    owner.add_pet(dog)
    return Scheduler(owner), dog


# ── Task tests ───────────────────────────────────────────────────────────────

def test_mark_complete_changes_status():
    task = Task("Walk", time="08:00", duration_minutes=30)
    assert task.completed is False
    task.mark_complete()
    assert task.completed is True


def test_mark_complete_once_returns_none():
    task = Task("Bath", time="09:00", duration_minutes=15, frequency="once")
    result = task.mark_complete()
    assert result is None


def test_daily_recurrence_creates_next_task():
    today = date.today()
    task = Task("Walk", time="08:00", duration_minutes=30, frequency="daily", next_due=today)
    next_task = task.mark_complete()
    assert next_task is not None
    assert next_task.next_due == today + timedelta(days=1)
    assert next_task.completed is False


def test_weekly_recurrence_creates_next_task():
    today = date.today()
    task = Task("Groom", time="10:00", duration_minutes=20, frequency="weekly", next_due=today)
    next_task = task.mark_complete()
    assert next_task is not None
    assert next_task.next_due == today + timedelta(weeks=1)


# ── Pet tests ────────────────────────────────────────────────────────────────

def test_add_task_increases_count():
    pet = Pet("Mochi", "dog")
    assert len(pet.tasks) == 0
    pet.add_task(Task("Walk", time="08:00", duration_minutes=30))
    assert len(pet.tasks) == 1


def test_remove_task_decreases_count():
    pet = Pet("Luna", "cat")
    pet.add_task(Task("Feed", time="07:00", duration_minutes=5))
    removed = pet.remove_task("Feed")
    assert removed is True
    assert len(pet.tasks) == 0


def test_remove_nonexistent_task_returns_false():
    pet = Pet("Luna", "cat")
    assert pet.remove_task("Bathe") is False


# ── Scheduler tests ──────────────────────────────────────────────────────────

def test_sort_by_time_is_chronological():
    scheduler, _ = make_scheduler()
    sorted_pairs = scheduler.sort_by_time()
    times = [t.time for _, t in sorted_pairs]
    assert times == sorted(times)


def test_filter_by_pet_returns_correct_tasks():
    scheduler, dog = make_scheduler()
    tasks = scheduler.filter_by_pet("Rex")
    assert len(tasks) == len(dog.tasks)


def test_filter_by_pet_unknown_returns_empty():
    scheduler, _ = make_scheduler()
    assert scheduler.filter_by_pet("Ghost") == []


def test_filter_by_status_incomplete():
    scheduler, _ = make_scheduler()
    incomplete = scheduler.filter_by_status(completed=False)
    assert all(not t.completed for _, t in incomplete)


def test_detect_conflicts_finds_duplicate_times():
    owner = Owner("Jo")
    pet = Pet("Max", "dog")
    pet.add_task(Task("Walk",     time="08:00", duration_minutes=30))
    pet.add_task(Task("Medicine", time="08:00", duration_minutes=5))
    owner.add_pet(pet)
    scheduler = Scheduler(owner)
    warnings = scheduler.detect_conflicts()
    assert len(warnings) == 1
    assert "08:00" in warnings[0]


def test_detect_no_conflicts():
    scheduler, _ = make_scheduler()
    # all tasks have distinct times: 07:00, 08:00, 10:00
    warnings = scheduler.detect_conflicts()
    assert warnings == []


def test_mark_task_complete_adds_recurrence():
    scheduler, dog = make_scheduler()
    before = len(dog.tasks)
    msg = scheduler.mark_task_complete("Rex", "Walk")
    assert "Next occurrence" in msg
    assert len(dog.tasks) == before + 1


def test_mark_task_complete_not_found():
    scheduler, _ = make_scheduler()
    msg = scheduler.mark_task_complete("Rex", "Nonexistent")
    assert "not found" in msg


def test_generate_schedule_structure():
    scheduler, _ = make_scheduler()
    schedule = scheduler.generate_schedule()
    assert len(schedule) > 0
    for entry in schedule:
        assert "time" in entry
        assert "task" in entry
        assert "pet" in entry
