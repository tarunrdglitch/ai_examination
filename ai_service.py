"""
Local LLM Service for AI Question Generation & Subjective Grading
Targets vLLM / Ollama OpenAI-compatible endpoints on DGX Spark LAN.
"""

import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

# Defaults point to local Spark endpoints (vLLM on port 8000 or Ollama on 11434)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:3b")  # default fallback or gemma/llama/qwen on Spark
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


def generate_questions_from_prompt(teacher_prompt, num_questions=5, question_type="both"):
    """
    Given a teacher's prompt/topic description, parse and generate structured questions.
    Returns list of question dicts:
    [{'type': 'objective'|'subjective', 'text': '...', 'marks': 1, 'options': [...], 'correct': 0, 'model_answer': '...', 'rubric': '...'}]
    """
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
