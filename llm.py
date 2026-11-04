import json, os, re, time
from dotenv import load_dotenv
from groq import Groq, RateLimitError, APIStatusError

load_dotenv()
MODEL = os.environ.get("MODEL", "openai/gpt-oss-20b")
_client = None


def client():
    global _client
    if _client is None:
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is missing. Add it to a .env file (see .env.example).")
        _client = Groq(api_key=key)
    return _client


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    return json.loads(text)


def chat_json(system, user, temperature=0.3, retries=3, max_tokens=1500):
    """One LLM call that must return a JSON object. Retries on rate limits and malformed JSON."""
    last_error = None
    for attempt in range(retries):
        try:
            r = client().chat.completions.create(
                model=MODEL, temperature=temperature, max_completion_tokens=max_tokens,
                reasoning_effort="low",  # remove this line if the API rejects it
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            return parse_json(r.choices[0].message.content)
        except (RateLimitError, APIStatusError) as e:
            last_error = e
            if getattr(e, "status_code", None) in (413, 429, 500, 503) and attempt < retries - 1:
                time.sleep(20 * (attempt + 1))
                continue
            raise
        except (json.JSONDecodeError, ValueError) as e:  # malformed JSON: just try again
            last_error = e
    raise RuntimeError(f"LLM did not return valid JSON after {retries} attempts: {last_error}")
