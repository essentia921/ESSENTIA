import os
import json
import asyncio
from typing import Optional, Any, Dict
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from backend.app.models.extractor import ExtractorApiLog


def _get_client() -> AsyncOpenAI:
    # OpenAI diretto (ex-integrazione Replit rimossa)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not configured (imposta OPENAI_API_KEY)")
    base_url = os.getenv("OPENAI_BASE_URL")  # opzionale: default = endpoint OpenAI
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


async def chat_json(
    system_prompt: str,
    user_prompt: str,
    model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini"),
    timeout: int = 120,
    job_id: Optional[str] = None,
    db: Optional[Session] = None,
    op: str = "chat_json"
) -> Dict[str, Any]:
    client = _get_client()
    start = asyncio.get_event_loop().time()
    request_data = {
        "model": model,
        "system": system_prompt[:500],
        "user_length": len(user_prompt),
        "op": op
    }

    for attempt in range(2):
        try:
            if attempt == 1:
                user_prompt = (
                    "The previous response was not valid JSON. "
                    "Please return ONLY valid JSON with no extra text.\n\n"
                    + user_prompt
                )

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                timeout=timeout
            )

            content = response.choices[0].message.content or "{}"
            duration_ms = int((asyncio.get_event_loop().time() - start) * 1000)

            result = json.loads(content)

            if job_id and db:
                _log(db, job_id, op, request_data, {"parsed": True, "keys": list(result.keys()), "attempt": attempt + 1}, 200, duration_ms)

            return result

        except json.JSONDecodeError:
            if attempt == 0:
                continue
            duration_ms = int((asyncio.get_event_loop().time() - start) * 1000)
            if job_id and db:
                _log(db, job_id, op, request_data, {"error": "Invalid JSON after repair attempt", "raw": content[:2000]}, 200, duration_ms)
            return {}

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start) * 1000)
            if job_id and db:
                _log(db, job_id, op, request_data, {"error": str(e)}, 500, duration_ms)
            if attempt == 0:
                await asyncio.sleep(2)
                continue
            raise


def _log(db: Session, job_id: str, op: str, request_data: dict, response_data: dict, status_code: int, duration_ms: int):
    try:
        req_str = json.dumps(request_data, default=str)
        resp_str = json.dumps(response_data, default=str)
        if len(resp_str) > 50000:
            resp_str = resp_str[:50000] + "...[truncated]"

        entry = ExtractorApiLog(
            job_id=job_id,
            log_type="ai",
            endpoint=op,
            request_data=req_str,
            response_data=resp_str,
            source="openai",
            status_code=status_code,
            duration_ms=duration_ms
        )
        db.add(entry)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
