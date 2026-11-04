# AI Interview Simulator (#evn-lf26-ai10)
Streamlit app where an LLM (Groq `openai/gpt-oss-20b`) interviews you for a chosen role and difficulty, evaluates every answer as structured JSON, computes a deterministic score in Python, and writes a final report.

## Run
pip install -r requirements.txt
Copy .env.example to .env and add GROQ_API_KEY
streamlit run app.py
python -m pytest -q     (tests for the scoring function)

## How it works
1. Setup: role + difficulty + number of questions. Difficulty changes question style (prompts.QUESTION_STYLE) and grading strictness (prompts.STRICTNESS).
2. Questions are generated one at a time; earlier questions are passed back so they are not repeated. The conversation lives in st.session_state.
3. Each answer is evaluated by the LLM into JSON: correctness, depth, clarity (0-10), strengths, weaknesses, feedback, red_flag. Output is validated and clamped in scoring.normalize_eval.
4. scoring.py computes the score: answer = 10 x (0.5*correctness + 0.3*depth + 0.2*clarity), minus 10 for a red flag; overall = mean; skipped = 0. The LLM never produces a score.
5. The report LLM sees only the structured evaluations and writes summary, strengths, weaknesses and an improvement plan. Each finished session is saved to samples/.

## Files
app.py (UI + flow), llm.py (Groq calls, retries), prompts.py, scoring.py, test_scoring.py, samples/ (captured sessions for 3+ roles), obstacle_log.md
