"""
Local LLM Service for AI Question Generation & Subjective Grading
Targets vLLM / Ollama OpenAI-compatible endpoints on DGX Spark LAN.
"""

import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

def get_llm_config():
    """Detects available Ollama or vLLM endpoints across host and container bridges."""
    custom_url = os.environ.get("LLM_BASE_URL")
    if custom_url:
        return custom_url.rstrip('/'), os.environ.get("LLM_MODEL", "nemotron-mini")

    # Candidates in order of likelihood (Docker bridge host -> Spark LAN IP -> localhost)
    candidates = [
        "http://172.18.0.1:11434",
        "http://192.168.10.252:11434",
        "http://127.0.0.1:11434",
        "http://127.0.0.1:8000"
    ]
    for base in candidates:
        try:
            r = requests.get(f"{base}/api/tags", timeout=0.8)
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                # Pick preferred model if available
                preferred = os.environ.get("LLM_MODEL")
                if not preferred:
                    for pref in ["nemotron-mini:latest", "nemotron-mini", "llama3.1:8b", "llama3.3:70b", "qwen2.5:3b"]:
                        if any(pref in m for m in models):
                            preferred = pref
                            break
                    if not preferred and models:
                        preferred = models[0]
                return f"{base}/v1", preferred or "nemotron-mini"
        except Exception:
            continue
    return "http://127.0.0.1:11434/v1", os.environ.get("LLM_MODEL", "nemotron-mini")


LLM_BASE_URL, LLM_MODEL = get_llm_config()
LLM_API_KEY = os.environ.get("LLM_API_KEY", "dummy-key")


def call_llm(messages, temperature=0.3, max_tokens=2048, response_format=None):
    """Call OpenAI-compatible chat completion endpoint on Spark."""
    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Error querying local LLM on Spark ({url}): {e}")
        return None


def extract_text_from_pdf(file_stream, start_page=None, end_page=None):
    """Extract clean text from an uploaded eBook PDF within an optional page range."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_stream)
        total_pages = len(reader.pages)
        
        start_idx = max(0, (start_page - 1) if start_page else 0)
        end_idx = min(total_pages, end_page if end_page else total_pages)
        
        extracted = []
        for i in range(start_idx, end_idx):
            page_text = reader.pages[i].extract_text()
            if page_text:
                extracted.append(f"--- [Page {i+1}] ---\n{page_text}")
                
        return "\n\n".join(extracted)
    except Exception as e:
        logger.error(f"Error parsing PDF eBook: {e}")
        return ""


def generate_questions_from_prompt(teacher_prompt, num_questions=5, question_type="both", context_text="", count=None):
    """
    Given a teacher's prompt/topic description and optional eBook context,
    generate structured questions.
    """
    if count is not None:
        num_questions = count

    sys_prompt = """You are an academic exam generation engine running locally on a private examination server.
Analyze the user request and generate questions accordingly in strict JSON format.
The JSON must adhere to the following schema:
{
  "questions": [
    {
      "type": "objective",
      "text": "Question statement here",
      "marks": 1,
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct": 0
    },
    {
      "type": "subjective",
      "text": "Detailed question prompt",
      "marks": 5,
      "model_answer": "Expected key concepts and breakdown",
      "rubric": "Marking breakdown (e.g. 2 marks definition, 3 marks explanation)"
    }
  ]
}
Rules:
1. Every objective question MUST have 4 options and 'correct' MUST be the 0-indexed integer of the right option.
2. Subjective questions MUST include 'model_answer' and 'rubric'.
3. Output ONLY the JSON block. No markdown wrapper if possible, or strictly within ```json ```.
"""

    user_msg = f"User Request: {teacher_prompt}\nTarget Question Count: {num_questions}\nRequested Format/Type: {question_type}"
    if context_text:
        # Limit to 12000 chars to avoid prompt context blowup
        user_msg += f"\n\nReference eBook/Syllabus Context:\n{context_text[:12000]}"

    res = call_llm([
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg}
    ], temperature=0.4, response_format={"type": "json_object"} if "vllm" in LLM_BASE_URL else None)

    if not res:
        return []

    try:
        # Strip codeblock wrappers if present
        clean_res = res.strip()
        if clean_res.startswith("```json"):
            clean_res = clean_res[7:]
        if clean_res.startswith("```"):
            clean_res = clean_res[3:]
        if clean_res.endswith("```"):
            clean_res = clean_res[:-3]
        clean_res = clean_res.strip()

        parsed = json.loads(clean_res)
        return parsed.get("questions", [])
    except Exception as e:
        logger.error(f"Failed to parse LLM generation JSON: {e}. Raw content: {res}")
        return []


def grade_subjective_answer(question_text, model_answer, rubric, max_marks, student_answer):
    """
    AI Grading for a subjective response.
    Returns: {'marks': float, 'feedback': str, 'confidence': float}
    """
    sys_prompt = """You are an objective and fair academic AI evaluator assisting educators.
Assess the student's answer against the question, model answer, and rubric.
Output strictly JSON:
{
  "marks": <float number between 0 and max_marks>,
  "feedback": "<concise breakdown of why marks were awarded or deducted>",
  "confidence": <float between 0.0 and 1.0>
}
"""
    user_msg = f"""Question: {question_text}
Max Marks: {max_marks}
Model Answer: {model_answer}
Rubric: {rubric}
Student's Answer: {student_answer}
"""
    res = call_llm([
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg}
    ], temperature=0.1)

    if not res:
        return {"marks": 0.0, "feedback": "AI grading server unreachable.", "confidence": 0.0}

    try:
        clean_res = res.strip()
        if clean_res.startswith("```json"):
            clean_res = clean_res[7:]
        if clean_res.startswith("```"):
            clean_res = clean_res[3:]
        if clean_res.endswith("```"):
            clean_res = clean_res[:-3]
        clean_res = clean_res.strip()

        data = json.loads(clean_res)
        marks = min(max(float(data.get("marks", 0.0)), 0.0), float(max_marks))
        return {
            "marks": marks,
            "feedback": data.get("feedback", ""),
            "confidence": float(data.get("confidence", 0.8))
        }
    except Exception as e:
        logger.error(f"Failed to parse AI grading JSON: {e}. Raw content: {res}")
        return {"marks": 0.0, "feedback": "Error parsing AI evaluation output.", "confidence": 0.0}
