"""AI Interview Simulator (Streamlit + Groq). Run: streamlit run app.py"""
import datetime, json, pathlib, re
import streamlit as st

import llm
from prompts import (ROLES, DIFFICULTIES, QUESTION_STYLE, STRICTNESS,
                     QUESTION_SYSTEM, EVAL_SYSTEM, REPORT_SYSTEM)
from scoring import normalize_eval, score_interview

SAMPLES_DIR = pathlib.Path(__file__).parent / "samples"
st.set_page_config(page_title="AI Interview Simulator", page_icon="🎤", layout="centered")


# ---------- state ----------
def init_state():
    defaults = {"stage": "setup", "role": "", "difficulty": "Medium", "n_questions": 5,
                "messages": [], "questions": [], "evals": [], "answers": [],
                "current_q": None, "report": None, "saved_path": None, "show_feedback": True}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def reset():
    for k in ["stage", "role", "messages", "questions", "evals", "answers", "current_q", "report", "saved_path"]:
        st.session_state.pop(k, None)
    init_state()


# ---------- LLM steps ----------
def generate_question():
    s = st.session_state
    prev = [f"{i+1}. [{q['topic']}] {q['question']}" for i, q in enumerate(s.questions)]
    user = (f"Role: {s.role}\nDifficulty: {s.difficulty} - {QUESTION_STYLE[s.difficulty]}\n"
            f"This is question {len(s.questions) + 1} of {s.n_questions}.\n"
            f"Earlier questions (do not repeat or overlap):\n" + ("\n".join(prev) if prev else "none"))
    data = llm.chat_json(QUESTION_SYSTEM, user, temperature=0.8, max_tokens=800)
    q = {"topic": str(data.get("topic", "General")).strip()[:40] or "General",
         "question": str(data.get("question", "")).strip()}
    if not q["question"]:
        raise RuntimeError("Question generator returned an empty question.")
    s.questions.append(q)
    s.current_q = q
    s.messages.append({"role": "assistant", "content": f"**Question {len(s.questions)}/{s.n_questions}** "
                                                       f"({q['topic']}): {q['question']}"})


def evaluate_answer(question, answer):
    s = st.session_state
    user = (f"Role: {s.role}\nDifficulty: {s.difficulty}\nStrictness: {STRICTNESS[s.difficulty]}\n\n"
            f"Question: {question['question']}\n\n<candidate_answer>\n{answer}\n</candidate_answer>")
    return normalize_eval(llm.chat_json(EVAL_SYSTEM, user, temperature=0.2, max_tokens=900))


def generate_report():
    s = st.session_state
    rows = []
    for q, a, e in zip(s.questions, s.answers, s.evals):
        rows.append({"topic": q["topic"], "question": q["question"], "answer_excerpt": a[:300],
                     "correctness": e["correctness"], "depth": e["depth"], "clarity": e["clarity"],
                     "strengths": e["strengths"], "weaknesses": e["weaknesses"], "skipped": e["skipped"],
                     "red_flag": e["red_flag"]})
    user = f"Role: {s.role}\nDifficulty: {s.difficulty}\nEvaluations:\n{json.dumps(rows, ensure_ascii=False)}"
    data = llm.chat_json(REPORT_SYSTEM, user, temperature=0.3, max_tokens=1800)
    lst = lambda k: [str(x) for x in data.get(k, []) if str(x).strip()] if isinstance(data.get(k), list) else []
    plan = [p for p in data.get("improvement_plan", []) if isinstance(p, dict)] if isinstance(data.get("improvement_plan"), list) else []
    return {"summary": str(data.get("summary", "")), "strengths": lst("strengths"),
            "weaknesses": lst("weaknesses"), "improvement_plan": plan}


# ---------- helpers ----------
def score_line(e):
    if e["skipped"]:
        return "Skipped"
    flag = " | red flag" if e["red_flag"] else ""
    return f"Correctness {e['correctness']}/10 | Depth {e['depth']}/10 | Clarity {e['clarity']}/10{flag}"


def report_markdown(score, report):
    s = st.session_state
    lines = [f"# Interview Report: {s.role} ({s.difficulty})", "",
             f"**Overall score: {score['overall']}/100 ({score['rating']})**", "", report["summary"], "",
             "## Score breakdown", f"_{score['formula']}_", ""]
    for k, v in score["dimension_averages"].items():
        lines.append(f"- {k.title()}: {v}/10")
    lines += ["", "| # | Topic | Score |", "|---|-------|-------|"]
    for i, (q, p) in enumerate(zip(s.questions, score["per_answer"]), 1):
        lines.append(f"| {i} | {q['topic']} | {p}/100 |")
    lines += ["", "## Strengths"] + [f"- {x}" for x in report["strengths"]]
    lines += ["", "## Weaknesses"] + [f"- {x}" for x in report["weaknesses"]]
    lines += ["", "## Improvement plan"]
    for p in report["improvement_plan"]:
        lines.append(f"- **{p.get('focus', '')}**: {p.get('action', '')} _(why: {p.get('why', '')})_")
    return "\n".join(lines)


def session_payload(score, report):
    s = st.session_state
    return {"timestamp": datetime.datetime.now().isoformat(timespec="seconds"), "model": llm.MODEL,
            "role": s.role, "difficulty": s.difficulty,
            "turns": [{"question": q, "answer": a, "evaluation": e}
                      for q, a, e in zip(s.questions, s.answers, s.evals)],
            "score": score, "report": report}


def save_sample(payload):
    SAMPLES_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", payload["role"].lower()).strip("_")
    path = SAMPLES_DIR / f"{slug}_{payload['difficulty'].lower()}_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path.name)


# ---------- screens ----------
def screen_setup():
    st.title("🎤 AI Interview Simulator")
    st.write("Pick a role and difficulty. Difficulty changes both the questions and how strictly answers are graded.")
    role = st.selectbox("Role", ROLES)
    if role == "Custom role...":
        role = st.text_input("Enter the role", placeholder="e.g. Cybersecurity Analyst").strip()
    difficulty = st.radio("Difficulty", DIFFICULTIES, index=1, horizontal=True)
    st.caption(f"Questions: {QUESTION_STYLE[difficulty]}")
    st.caption(f"Grading: {STRICTNESS[difficulty]}")
    n = st.slider("Number of questions", 3, 8, 5)
    st.session_state.show_feedback = st.checkbox("Show feedback after each answer", value=True)
    if st.button("Start interview", type="primary", disabled=not role):
        s = st.session_state
        s.role, s.difficulty, s.n_questions = role, difficulty, n
        s.messages = [{"role": "assistant", "content": f"Welcome! I'll be interviewing you for a **{role}** position "
                                                       f"at **{difficulty}** difficulty. {n} questions. Let's begin."}]
        try:
            with st.spinner("Preparing the first question..."):
                generate_question()
        except Exception as e:
            st.error(f"Could not generate a question: {e}")
            return
        s.stage = "interview"
        st.rerun()


def finish_answer(answer, skipped=False):
    """Evaluate the answer, record it, then either ask the next question or move to the report."""
    s = st.session_state
    q = s.current_q
    try:
        with st.spinner("Evaluating your answer..."):
            ev = normalize_eval(None, skipped=True) if skipped else evaluate_answer(q, answer)
        s.answers.append("" if skipped else answer)
        s.evals.append(ev)
        if s.show_feedback:
            fb = score_line(ev) + ("" if skipped else f"\n\n{ev['feedback']}")
            s.messages.append({"role": "assistant", "content": f"_Feedback_: {fb}"})
        if len(s.evals) >= s.n_questions:
            s.stage = "report"
        else:
            with st.spinner("Next question..."):
                generate_question()
    except Exception as e:
        st.error(f"Something went wrong: {e}. Your answer was not recorded; please try again.")
        return
    st.rerun()


def screen_interview():
    s = st.session_state
    st.title(f"Interview: {s.role}")
    st.caption(f"Difficulty: {s.difficulty}")
    st.progress(len(s.evals) / s.n_questions, text=f"{len(s.evals)}/{s.n_questions} answered")
    for m in s.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    col1, col2 = st.columns(2)
    if col1.button("Skip question"):
        finish_answer("", skipped=True)
    if col2.button("End interview early", disabled=len(s.evals) == 0):
        s.stage = "report"
        st.rerun()
    answer = st.chat_input("Type your answer...")
    if answer and answer.strip():
        s.messages.append({"role": "user", "content": answer.strip()})
        with st.chat_message("user"):
            st.markdown(answer.strip())
        finish_answer(answer.strip())


def screen_report():
    s = st.session_state
    st.title("📊 Performance Report")
    score = score_interview(s.evals)
    if s.report is None:
        try:
            with st.spinner("Writing your report..."):
                s.report = generate_report()
        except Exception as e:
            st.error(f"Could not write the report: {e}")
            if st.button("Retry"):
                st.rerun()
            return
        s.saved_path = save_sample(session_payload(score, s.report))
    report = s.report
    c1, c2 = st.columns(2)
    c1.metric("Overall score", f"{score['overall']}/100")
    c2.metric("Rating", score["rating"])
    st.write(report["summary"])
    st.subheader("How the score was calculated")
    st.caption(score["formula"])
    for k, v in score["dimension_averages"].items():
        st.progress(v / 10, text=f"{k.title()}: {v}/10")
    st.dataframe([{"#": i, "Topic": q["topic"], "Correctness": e["correctness"], "Depth": e["depth"],
                   "Clarity": e["clarity"], "Red flag": e["red_flag"], "Score /100": p}
                  for i, (q, e, p) in enumerate(zip(s.questions, s.evals, score["per_answer"]), 1)],
                 hide_index=True, use_container_width=True)
    st.subheader("Strengths")
    for x in report["strengths"]:
        st.markdown(f"- {x}")
    st.subheader("Weaknesses")
    for x in report["weaknesses"]:
        st.markdown(f"- {x}")
    st.subheader("Improvement plan")
    for p in report["improvement_plan"]:
        st.markdown(f"- **{p.get('focus', '')}**: {p.get('action', '')}  \n  _Why: {p.get('why', '')}_")
    md = report_markdown(score, report)
    st.download_button("Download report (.md)", md, file_name="interview_report.md")
    st.download_button("Download session (.json)", json.dumps(session_payload(score, report), indent=2, ensure_ascii=False),
                       file_name="interview_session.json")
    if s.saved_path:
        st.caption(f"Session auto-saved to samples/{s.saved_path}")
    if st.button("Start a new interview"):
        reset()
        st.rerun()


init_state()
try:
    llm.client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

{"setup": screen_setup, "interview": screen_interview, "report": screen_report}[st.session_state.stage]()
