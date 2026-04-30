"""PawPal+ — Streamlit UI connected to the backend logic layer."""

import streamlit as st
from datetime import date
from dotenv import load_dotenv

from pawpal_system import Owner, Pet, Task, Scheduler
from rag.pipeline import RAGPipeline, RAGResponse

load_dotenv()

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# ── Session state bootstrap ──────────────────────────────────────────────────
if "owner" not in st.session_state:
    st.session_state.owner = None
if "scheduler" not in st.session_state:
    st.session_state.scheduler = None
if "schedule_explanation" not in st.session_state:
    st.session_state.schedule_explanation = None
if "ask_history" not in st.session_state:
    st.session_state.ask_history = []  # list[(question, RAGResponse)]


# ── RAG pipeline (cached so the model only loads once per session) ──────────
@st.cache_resource(show_spinner="Loading PawPal's pet-care knowledge base...")
def get_rag_pipeline() -> RAGPipeline | None:
    """Build the RAG pipeline once. Returns None if setup fails."""
    try:
        return RAGPipeline()
    except Exception as e:
        st.session_state["rag_error"] = str(e)
        return None


def render_rag_response(response: RAGResponse) -> None:
    """Display a RAG answer with its confidence badge and source list."""
    conf = response.confidence
    if conf.label == "high":
        st.success(f"🟢 {conf.display()} — {conf.reasoning}")
    elif conf.label == "medium":
        st.info(f"🟡 {conf.display()} — {conf.reasoning}")
    else:
        st.warning(f"🟠 {conf.display()} — {conf.reasoning}")

    st.markdown(response.answer)

    if response.retrieval:
        with st.expander("Retrieved sources", expanded=False):
            for r in response.retrieval:
                st.markdown(
                    f"- **{r.document.citation()}** "
                    f"_(similarity {r.score:.2f})_"
                )

    if response.error:
        st.error(f"⚠ Error: {response.error}")

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🐾 PawPal+")
st.caption("A smart daily pet care planner.")

# ── Step 1: Owner setup ───────────────────────────────────────────────────────
with st.expander("1️⃣  Owner Setup", expanded=st.session_state.owner is None):
    owner_name = st.text_input("Owner name", value="Jordan")
    if st.button("Save owner"):
        st.session_state.owner = Owner(owner_name)
        st.session_state.scheduler = Scheduler(st.session_state.owner)
        st.success(f"Welcome, {owner_name}!")

if st.session_state.owner is None:
    st.info("Enter your name above to get started.")
    st.stop()

owner: Owner = st.session_state.owner
scheduler: Scheduler = st.session_state.scheduler

# ── Step 2: Add pets ──────────────────────────────────────────────────────────
with st.expander("2️⃣  Add a Pet"):
    col1, col2 = st.columns(2)
    with col1:
        pet_name = st.text_input("Pet name", key="new_pet_name")
    with col2:
        species = st.selectbox("Species", ["dog", "cat", "rabbit", "bird", "other"], key="new_species")

    if st.button("Add pet"):
        existing = [p.name.lower() for p in owner.pets]
        if pet_name.strip() == "":
            st.warning("Please enter a pet name.")
        elif pet_name.lower() in existing:
            st.warning(f"{pet_name} is already added.")
        else:
            owner.add_pet(Pet(pet_name, species))
            st.success(f"Added {pet_name} the {species}!")

if owner.pets:
    st.markdown(f"**Pets:** {', '.join(p.name for p in owner.pets)}")

# ── Step 3: Add tasks ─────────────────────────────────────────────────────────
with st.expander("3️⃣  Add a Task"):
    if not owner.pets:
        st.info("Add a pet first.")
    else:
        pet_choice = st.selectbox("Assign to", [p.name for p in owner.pets], key="task_pet")
        col1, col2 = st.columns(2)
        with col1:
            task_desc = st.text_input("Task description", value="Morning walk", key="task_desc")
            task_time = st.text_input("Time (HH:MM)", value="08:00", key="task_time")
            duration = st.number_input("Duration (minutes)", min_value=1, max_value=480, value=30, key="task_dur")
        with col2:
            priority = st.selectbox("Priority", ["high", "medium", "low"], key="task_pri")
            frequency = st.selectbox("Frequency", ["daily", "weekly", "once"], key="task_freq")

        if st.button("Add task"):
            # Validate HH:MM
            parts = task_time.split(":")
            valid_time = (
                len(parts) == 2
                and parts[0].isdigit() and parts[1].isdigit()
                and 0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59
            )
            if task_desc.strip() == "":
                st.warning("Please enter a task description.")
            elif not valid_time:
                st.warning("Time must be in HH:MM format (e.g. 08:30).")
            else:
                pet_obj = next(p for p in owner.pets if p.name == pet_choice)
                pet_obj.add_task(Task(
                    description=task_desc,
                    time=task_time,
                    duration_minutes=int(duration),
                    priority=priority,
                    frequency=frequency,
                    next_due=date.today(),
                ))
                st.success(f"Task '{task_desc}' added to {pet_choice}.")

# ── Step 4: Generate schedule ─────────────────────────────────────────────────
st.divider()
st.subheader("📋 Today's Schedule")

if not owner.pets or all(len(p.tasks) == 0 for p in owner.pets):
    st.info("Add pets and tasks above, then your schedule will appear here.")
else:
    # Conflict warnings
    conflicts = scheduler.detect_conflicts()
    if conflicts:
        for w in conflicts:
            st.warning(f"⚠ {w}")

    schedule = scheduler.generate_schedule()
    if schedule:
        # Build display table
        import pandas as pd
        df = pd.DataFrame(schedule)
        df.rename(columns={
            "time": "Time",
            "pet": "Pet",
            "task": "Task",
            "duration": "Duration",
            "priority": "Priority",
            "frequency": "Frequency",
            "done": "Done",
        }, inplace=True)
        df["Done"] = df["Done"].map({True: "✓", False: "○"})
        st.dataframe(df, use_container_width=True, hide_index=True)

        # ── Explain this schedule (RAG) ──────────────────────────────────
        col_a, col_b = st.columns([1, 3])
        with col_a:
            explain_clicked = st.button("🤖 Explain this schedule", use_container_width=True)
        with col_b:
            if st.session_state.schedule_explanation is not None:
                if st.button("Clear explanation", use_container_width=True):
                    st.session_state.schedule_explanation = None
                    st.rerun()

        if explain_clicked:
            pipeline = get_rag_pipeline()
            if pipeline is None:
                st.error(
                    "RAG pipeline unavailable. Make sure GEMINI_API_KEY is set "
                    "in your .env file. See .env.example for a template."
                )
            else:
                with st.spinner("PawPal is reasoning about your schedule..."):
                    st.session_state.schedule_explanation = pipeline.explain_schedule(schedule)

        if st.session_state.schedule_explanation is not None:
            st.markdown("##### 🐾 PawPal's take")
            render_rag_response(st.session_state.schedule_explanation)
    else:
        st.info("No tasks scheduled yet.")

# ── Step 5: Mark complete ─────────────────────────────────────────────────────
with st.expander("✅  Mark a Task Complete"):
    if not owner.pets:
        st.info("No pets added yet.")
    else:
        mc_pet = st.selectbox("Pet", [p.name for p in owner.pets], key="mc_pet")
        pet_tasks = scheduler.filter_by_pet(mc_pet)
        incomplete = [t for t in pet_tasks if not t.completed]
        if not incomplete:
            st.success("All tasks for this pet are complete!")
        else:
            mc_task = st.selectbox("Task", [t.description for t in incomplete], key="mc_task")
            if st.button("Mark complete"):
                msg = scheduler.mark_task_complete(mc_pet, mc_task)
                if "Next occurrence" in msg:
                    st.success(msg)
                else:
                    st.success(msg)
                st.rerun()

# ── Step 6: Filter view ───────────────────────────────────────────────────────
with st.expander("🔍  Filter Tasks"):
    col1, col2 = st.columns(2)
    with col1:
        show_pet = st.selectbox("By pet", ["All"] + [p.name for p in owner.pets], key="filter_pet")
    with col2:
        show_status = st.selectbox("By status", ["All", "Incomplete", "Complete"], key="filter_status")

    if show_pet == "All" and show_status == "All":
        results = [(pet, task) for pet in owner.pets for task in pet.tasks]
    elif show_pet != "All" and show_status == "All":
        results = [(next(p for p in owner.pets if p.name == show_pet), t)
                   for t in scheduler.filter_by_pet(show_pet)]
    elif show_pet == "All" and show_status != "All":
        done = show_status == "Complete"
        results = scheduler.filter_by_status(done)
    else:
        done = show_status == "Complete"
        results = [(next(p for p in owner.pets if p.name == show_pet), t)
                   for t in scheduler.filter_by_pet(show_pet) if t.completed == done]

    if results:
        for pet, task in results:
            status_icon = "✓" if task.completed else "○"
            st.markdown(
                f"`{task.time}` **{pet.name}** — {task.description} "
                f"({task.duration_minutes} min, {task.priority}) {status_icon}"
            )
    else:
        st.info("No tasks match this filter.")

# ── Step 7: Ask PawPal (RAG Q&A) ──────────────────────────────────────────────
st.divider()
st.subheader("💬 Ask PawPal")
st.caption(
    "Ask any pet-care question. PawPal retrieves relevant passages from its "
    "knowledge base and answers using only those sources."
)

with st.form("ask_form", clear_on_submit=False):
    question = st.text_input(
        "Your question",
        placeholder="e.g. How often should I bathe a Maltese?",
        key="ask_question",
    )
    submitted = st.form_submit_button("Ask")

if submitted and question.strip():
    pipeline = get_rag_pipeline()
    if pipeline is None:
        st.error(
            "RAG pipeline unavailable. Make sure GEMINI_API_KEY is set in your "
            ".env file. See .env.example for a template."
        )
    else:
        with st.spinner("Retrieving sources and generating answer..."):
            response = pipeline.ask(question)
        st.session_state.ask_history.insert(0, (question, response))

if st.session_state.ask_history:
    st.markdown("---")
    for i, (q, resp) in enumerate(st.session_state.ask_history[:5]):
        st.markdown(f"**Q:** {q}")
        render_rag_response(resp)
        if i < min(len(st.session_state.ask_history), 5) - 1:
            st.markdown("---")
    if len(st.session_state.ask_history) > 5:
        st.caption(
            f"Showing 5 most recent of {len(st.session_state.ask_history)} questions."
        )
