"""LLM Advisors debate orchestrator."""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional

from .council import query_model
from .costs import build_advisor_cost_report
from .providers.errors import describe_exception
from .model_preflight import build_preflight_error_message, preflight_models
from .personas import get_personas_by_ids, get_persona, Persona
from .settings import get_settings
from .advisor_prompts import (
    ADVISOR_ROUND1_PROMPT,
    ADVISOR_FOLLOWUP_PROMPT,
    ADVISOR_CROSS_POLLINATION_PROMPT,
    ADVISOR_VERDICT_PROMPT,
    ADVISOR_TIEBREAKER_PROMPT,
    CONSENSUS_TAG_INSTRUCTION,
)
from .prompts import apply_response_language
from .review_scoring import group_config, consume_score, build_score_report, score_markdown, combine_verdict

logger = logging.getLogger(__name__)


def parse_consensus_tag(content: str) -> Optional[int]:
    """Extract CONSENSUS_SCORE: 1-5 from the end of a response."""
    if not content:
        return None
    match = re.search(r"CONSENSUS_SCORE:\s*\[?([1-5])\]?\s*$", content.strip(), re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def strip_consensus_tag(content: str) -> str:
    """Remove the CONSENSUS_SCORE tag from the response for display."""
    if not content:
        return content
    return re.sub(r"\n*CONSENSUS_SCORE:\s*\[?[1-5]\]?\s*$", "", content.strip(), flags=re.IGNORECASE).strip()


def build_rotation_order(persona_ids: List[str], round_number: int) -> List[str]:
    """Rotate speaking order for each round. Round 1 = original order, Round 2 = shift left by 1, etc."""
    n = len(persona_ids)
    shift = (round_number - 1) % n
    return persona_ids[shift:] + persona_ids[:shift]


def _format_transcript(rounds: List[Dict[str, Any]], personas: Dict[str, Persona]) -> str:
    """Format the debate transcript for injection into prompts."""
    lines = []
    for r in rounds:
        lines.append(f"--- Round {r['round_number']} ---")
        for resp in r["responses"]:
            p = personas.get(resp["persona_id"])
            name = p.name if p else resp["persona_id"]
            role = p.role if p else ""
            if resp.get('error'):
                lines.append(f"\n{name} ({role}): 本轮返回失败，未收到意见；不能据此推断赞同或反对。")
            else:
                lines.append(f"\n{name} ({role}):\n{resp.get('content') or '本轮没有可用内容'}")
    return "\n".join(lines)


def _average_consensus_score(scores: Dict[str, Optional[int]]) -> Optional[float]:
    numeric_scores = [score for score in scores.values() if isinstance(score, int)]
    if not numeric_scores:
        return None
    return round(sum(numeric_scores) / len(numeric_scores), 2)


def _count_words(content: str) -> int:
    """Count display words for advisor response limit enforcement."""
    if not content:
        return 0
    return len(re.findall(r"\b[\w'-]+\b", content))


def _settings_prompt(settings: Any, key: str, default: str) -> str:
    """Return a saved prompt template, falling back to the built-in default."""
    prompt = getattr(settings, key, None)
    if isinstance(prompt, str) and prompt.strip():
        return prompt
    return default


def _format_debate_arc(
    all_rounds: List[Dict[str, Any]],
    personas: Dict[str, Persona],
    round_extracts: List[Dict[str, Any]],
    consensus_reached: bool,
    consensus_round: Optional[int],
) -> str:
    """Build a compact debate-arc signal for the verdict model."""
    if not all_rounds:
        return "No completed rounds."

    first_round = all_rounds[0]
    final_round = all_rounds[-1]
    first_extract = round_extracts[0]["content"] if round_extracts else "No distilled Round 1 summary was produced."

    lines = [
        f"Consensus reached: {'yes' if consensus_reached else 'no'}",
        f"Consensus round: {consensus_round if consensus_round else 'none'}",
        f"Final round average consensus score: {final_round.get('average_consensus_score')}",
        "",
        "Round 1 summary:",
        first_extract,
        "",
        "Final round summary:",
    ]

    for resp in final_round.get("responses", []):
        pid = resp["persona_id"]
        persona = personas.get(pid)
        name = persona.name if persona else resp.get("persona_name", pid)
        content = (resp.get("content") or "").strip().replace("\n", " ")
        summary = content[:300] + ("..." if len(content) > 300 else "")
        lines.append(
            f"- {name}: {summary} Final consensus score: {resp.get('consensus_score')}"
        )

    lines.extend(["", "Starting vs final positions:"])
    first_by_pid = {resp["persona_id"]: resp for resp in first_round.get("responses", [])}
    final_by_pid = {resp["persona_id"]: resp for resp in final_round.get("responses", [])}
    for pid, final_resp in final_by_pid.items():
        persona = personas.get(pid)
        name = persona.name if persona else final_resp.get("persona_name", pid)
        start = (first_by_pid.get(pid, {}).get("content") or "").strip().replace("\n", " ")
        final = (final_resp.get("content") or "").strip().replace("\n", " ")
        start_summary = start[:220] + ("..." if len(start) > 220 else "")
        final_summary = final[:220] + ("..." if len(final) > 220 else "")
        lines.append(
            f"- {name}: starting position: {start_summary}; "
            f"final position: {final_summary}; Final consensus score: {final_resp.get('consensus_score')}"
        )

    return "\n".join(lines)


def _resolve_model(
    persona_id: str,
    model_assignments: Optional[Dict[str, str]],
    default_model: str,
) -> str:
    """Determine which model to use for a given persona."""
    if model_assignments and persona_id in model_assignments:
        return model_assignments[persona_id]
    return default_model


async def _query_advisor(
    pid: str,
    prompt: str,
    personas_map: Dict[str, Persona],
    model_assignments: Optional[Dict[str, str]],
    default_model: str,
    temperature: float,
    conversation_id: Optional[str] = None,
) -> tuple:
    persona = personas_map[pid]
    model = _resolve_model(pid, model_assignments, default_model)
    messages = [
        {"role": "system", "content": persona.system_prompt},
        {"role": "user", "content": prompt},
    ]
    try:
        result = await query_model(
            model,
            messages,
            temperature=temperature,
            conversation_id=conversation_id,
        )
        if result.get("error"):
            return pid, model, None, result.get("error_message") or "模型接口失败，未提供原因", result.get("usage"), result.get("cost")
        return pid, model, result.get("content", ""), None, result.get("usage"), result.get("cost")
    except Exception as e:
        return pid, model, None, describe_exception(e), None, None


def _unpack_advisor_result(result: tuple) -> tuple:
    """Accept old four-field test doubles while using six fields in production."""
    if len(result) == 4:
        pid, model, content, error = result
        return pid, model, content, error, None, None
    return result


async def _query_neutral(
    model: str,
    prompt: str,
    temperature: float = 0.3,
    conversation_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Call a neutral (non-persona) model and return a normalized result dict."""
    try:
        response = await query_model(
            model,
            ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [{"role": "user", "content": prompt}],
            temperature=temperature,
            conversation_id=conversation_id,
        )
        if response.get("error"):
            return {
                "model": model,
                "content": None,
                "error": response.get("error_message"),
                "usage": response.get("usage"),
                "cost": response.get("cost"),
            }
        return {
            "model": model,
            "content": response.get("content", ""),
            "error": None,
            "usage": response.get("usage"),
            "cost": response.get("cost"),
        }
    except Exception as e:
        return {"model": model, "content": None, "error": str(e), "usage": None, "cost": None}


async def run_debate(
    question: str,
    persona_ids: List[str],
    model_assignments: Optional[Dict[str, str]] = None,
    default_model: Optional[str] = None,
    tiebreaker_model: Optional[str] = None,
    max_rounds: int = 3,
    web_search: bool = False,
    search_context: str = "",
    request: Any = None,
    preflight: bool = False,
    conversation_id: Optional[str] = None,
    round_policy: str = "adaptive",
):
    """
    Run a multi-round advisor debate.

    Async generator yielding SSE-compatible event dicts.

    Args:
        question: The question to debate
        persona_ids: List of persona IDs to participate (2-8; chair excluded)
        model_assignments: Optional per-persona model mapping
        default_model: Fallback model for all personas
        max_rounds: Fixed review rounds (1-10) or adaptive upper bound (3-10)
        web_search: Whether web search was used
        search_context: Pre-fetched search results
        request: FastAPI request for disconnect detection
    """
    settings = get_settings()
    temperature = settings.advisor_temperature
    chair_id = getattr(settings, "advisor_chair_persona_id", "")
    chair = get_persona(chair_id) if chair_id else None
    if chair_id and not chair:
        yield {"type": "advisor_error", "message": "Chair persona not found. Select a chair again."}
        return
    if chair:
        persona_ids = [pid for pid in persona_ids if pid != chair.id]

    if not default_model:
        default_model = settings.advisor_default_model
    if not default_model:
        yield {"type": "advisor_error", "message": "No advisor model configured. Set a default model in Settings."}
        return
    minimum = 1 if round_policy == "fixed" else 3
    if round_policy not in {"fixed", "adaptive"} or type(max_rounds) is not int or not minimum <= max_rounds <= 10:
        yield {"type": "advisor_error", "message": f"Rounds must be between {minimum} and 10 for {round_policy} policy."}
        return

    personas_list = get_personas_by_ids(persona_ids)
    if len(personas_list) < 2:
        yield {"type": "advisor_error", "message": "At least 2 valid advisors required."}
        return

    personas_map = {p.id: p for p in personas_list}
    personas_serialized = []
    for p in personas_list:
        p_dict = p.model_dump()
        p_dict["model"] = _resolve_model(p.id, model_assignments, default_model)
        personas_serialized.append(p_dict)
    verdict_model = tiebreaker_model or settings.advisor_tiebreaker_model or default_model

    if preflight:
        models_to_check = [p["model"] for p in personas_serialized]
        models_to_check.append(verdict_model)
        preflight_result = await preflight_models(
            models_to_check,
            conversation_id=conversation_id,
        )
        if not preflight_result.ok:
            yield {
                "type": "advisor_error",
                "message": build_preflight_error_message(preflight_result),
            }
            return

    search_context_block = ""
    if search_context:
        search_context_block = (
            "You have access to the following real-time web search results. "
            "Use this information if relevant to the debate.\n\n"
            f"Search Results:\n{search_context}\n\n"
        )

    yield {
        "type": "advisor_debate_start",
        "data": {
            "personas": personas_serialized,
            "max_rounds": max_rounds,
            "round_policy": round_policy,
            "question": question,
            "web_search": web_search,
        },
    }

    # .format substitutes values once; braces inside the manuscript are data.
    # Escaping them here changed code examples and later quote matching.
    safe_question = question

    all_rounds: List[Dict[str, Any]] = []
    cost_rounds: List[Dict[str, Any]] = []
    round_extracts: List[Dict[str, Any]] = []
    consensus_reached = False
    consensus_round: Optional[int] = None
    extract_model = verdict_model
    review_panel = all(group_config(p.system_prompt) for p in personas_list)
    # A single local/custom endpoint often queues all five reasoning calls.
    # Bound review concurrency and retry only transient transport/service errors.
    review_slots = asyncio.Semaphore(2) if review_panel else asyncio.Semaphore(len(persona_ids))

    async def query_review(pid, prompt, kwargs):
        attempts = 0
        history = []
        while True:
            attempts += 1
            async with review_slots:
                result = _unpack_advisor_result(await _query_advisor(
                    pid, prompt, personas_map, model_assignments, default_model,
                    temperature, **kwargs))
            failure = str(result[3] or '')
            history.append({'model':result[1], 'usage':result[4], 'cost':result[5]})
            permanent = bool(re.search(r'\b(?:400|401|403|404|422)\b',failure))
            transient = not permanent and bool(re.search(r'time[ -]?out|timed out|429|\b50[0234]\b|connect|connection|temporar|超时|繁忙|过载|连接.*(?:中断|断开|提前结束)', failure, re.I))
            if not (review_panel and transient and attempts < 2):
                return result, history
            await asyncio.sleep(3)

    for round_num in range(1, max_rounds + 1):
        if request and await request.is_disconnected():
            logger.info("Client disconnected during advisor debate.")
            return

        is_first_round = round_num == 1
        order = build_rotation_order(persona_ids, round_num)

        yield {
            "type": "advisor_round_start",
            "data": {"round_number": round_num, "order": order, "is_parallel": True},
        }

        round_responses: List[Dict[str, Any]] = []
        consensus_votes: Dict[str, bool] = {}
        consensus_scores: Dict[str, Optional[int]] = {}
        word_limit = 150 if is_first_round else 250

        if is_first_round:
            prompt_template = _settings_prompt(
                settings, "advisor_round1_prompt", ADVISOR_ROUND1_PROMPT
            ).format(
                search_context_block=search_context_block,
                question=safe_question,
                consensus_tag=CONSENSUS_TAG_INSTRUCTION,
            )
        else:
            transcript_text = _format_transcript(all_rounds, personas_map)
            previous_extract = (
                round_extracts[-1]["content"]
                if round_extracts and round_extracts[-1].get("content")
                else "No distilled extract was produced for the previous round. Use the transcript as fallback context."
            )
            prompt_template = _settings_prompt(
                settings, "advisor_followup_prompt", ADVISOR_FOLLOWUP_PROMPT
            ).format(
                search_context_block=search_context_block if round_num == 2 else "",
                question=safe_question,
                transcript=transcript_text,
                round_number=round_num,
                previous_round_number=round_num - 1,
                cross_pollination_extract=previous_extract,
                consensus_tag=CONSENSUS_TAG_INSTRUCTION,
            )

        if round_policy == "fixed":
            stage = "独立审阅完整原稿" if is_first_round else "交叉复核上一轮实际意见" if round_num == 2 else "收束仍成立的意见，撤回误读与重复要求"
            prompt_template += f"\n【固定审阅第{round_num}/{max_rounds}轮】本轮任务：{stage}。不为完成轮数编造新问题；没有新增可明确保留或收窄已有判断。最后才由主编统一汇总。"
        localized_prompt = apply_response_language(prompt_template, settings.response_language)

        advisor_kwargs = {}
        if conversation_id is not None:
            advisor_kwargs["conversation_id"] = conversation_id
        tasks = [asyncio.create_task(query_review(pid, localized_prompt, advisor_kwargs)) for pid in order]

        pending = set(tasks)
        completed_count = 0
        try:
            while pending:
                if request and await request.is_disconnected():
                    for t in pending:
                        t.cancel()
                    return

                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED, timeout=1.0
                )

                for task in done:
                    result, attempt_history = await task
                    attempts = len(attempt_history)
                    pid, model, content, error, usage, cost = result
                    if not error and (not isinstance(content, str) or not content.strip()):
                        error = '模型返回空内容，本团没有生成可用意见'
                    completed_count += 1

                    if error:
                        resp_data = {
                            "persona_id": pid,
                            "persona_name": personas_map[pid].name,
                            "model": model,
                            "content": None,
                            "error": error,
                            "consensus": False,
                            "consensus_score": None,
                            "usage": usage,
                            "cost": cost,
                        }
                    else:
                        consensus_score = parse_consensus_tag(content)
                        clean_content = strip_consensus_tag(content)
                        clean_content, review_rating = consume_score(
                            clean_content, group_config(personas_map[pid].system_prompt), safe_question
                        )
                        word_count = _count_words(clean_content)
                        exceeds_word_limit = word_count > word_limit
                        has_consensus = (
                            consensus_score is not None
                            and consensus_score >= 4
                        )
                        response_warning = (
                            f"Advisor response exceeded the {word_limit} word guidance and was kept."
                            if exceeds_word_limit
                            else None
                        )
                        consensus_votes[pid] = has_consensus
                        consensus_scores[pid] = consensus_score
                        resp_data = {
                            "persona_id": pid,
                            "persona_name": personas_map[pid].name,
                            "model": model,
                            "content": clean_content,
                            "review_rating": review_rating,
                            "error": None,
                            "warning": response_warning,
                            "consensus": has_consensus,
                            "consensus_score": consensus_score,
                            "word_count": word_count,
                            "word_limit": word_limit,
                            "word_limit_exceeded": exceeds_word_limit,
                            "usage": usage,
                            "cost": cost,
                        }

                    resp_data['attempts'] = attempts
                    resp_data['attempt_history'] = attempt_history
                    round_responses.append(resp_data)

                    yield {
                        "type": "advisor_response",
                        "data": resp_data,
                        "round": round_num,
                        "count": completed_count,
                        "total": len(order),
                    }

        except asyncio.CancelledError:
            for t in tasks:
                if not t.done():
                    t.cancel()
            return

        successful_responses = [r for r in round_responses if r["error"] is None]
        average_consensus_score = _average_consensus_score(consensus_scores)
        all_rounds.append({
            "round_number": round_num,
            "average_consensus_score": average_consensus_score,
            "complete": True,
            "responses": list(round_responses),
        })
        cost_rounds.append({
            "round_number": round_num,
            "responses": round_responses,
        })

        all_agree = (
            len(successful_responses) == len(personas_list)
            and len(consensus_scores) == len(personas_list)
            and all(score is not None and score >= 4 for score in consensus_scores.values())
        )
        consensus_reached = all_agree
        consensus_round = round_num if all_agree else None

        yield {
            "type": "advisor_round_complete",
            "data": {
                "round_number": round_num,
                "responses": round_responses,
                "consensus_votes": dict(consensus_votes),
                "consensus_scores": dict(consensus_scores),
                "average_consensus_score": average_consensus_score,
                "consensus_reached": all_agree,
            },
        }

        if review_panel and not successful_responses:
            # An empty round cannot be cross-reviewed; preserve its failures.
            break

        if all_agree and round_policy == "adaptive":
            break

        if round_num < max_rounds:
            if request and await request.is_disconnected():
                logger.info("Client disconnected during advisor extract.")
                return
            round_transcript = _format_transcript([all_rounds[-1]], personas_map)
            extract_prompt = _settings_prompt(
                settings,
                "advisor_cross_pollination_prompt",
                ADVISOR_CROSS_POLLINATION_PROMPT,
            ).format(
                question=safe_question,
                round_number=round_num,
                round_transcript=round_transcript,
            )
            extract_result = await _query_neutral(
                extract_model,
                apply_response_language(extract_prompt, settings.response_language),
                temperature=0.2,
                conversation_id=conversation_id,
            )
            if extract_result.get("error") or not extract_result.get("content"):
                yield {
                    "type": "advisor_error",
                    "message": (
                        "Cross-pollination extract failed after "
                        f"Round {round_num}: {extract_result.get('error') or 'empty response'}"
                    ),
                }
                return
            round_extracts.append({
                "round_number": round_num,
                "model": extract_result.get("model"),
                "content": extract_result.get("content") or "",
                "error": extract_result.get("error"),
                "usage": extract_result.get("usage"),
                "cost": extract_result.get("cost"),
            })

    transcript_text = _format_transcript(all_rounds, personas_map)

    tiebreaker_result = None
    if round_policy == "adaptive" and not consensus_reached and len(persona_ids) == 2:
        yield {"type": "advisor_tiebreaker_start"}

        tiebreaker_prompt = _settings_prompt(
            settings, "advisor_tiebreaker_prompt", ADVISOR_TIEBREAKER_PROMPT
        ).format(
            question=safe_question,
            transcript=transcript_text,
        )
        tiebreaker_result = await _query_neutral(
            verdict_model,
            apply_response_language(tiebreaker_prompt, settings.response_language),
            conversation_id=conversation_id,
        )

        yield {"type": "advisor_tiebreaker", "data": tiebreaker_result}

    yield {"type": "advisor_verdict_start"}

    debate_arc = _format_debate_arc(
        all_rounds,
        personas_map,
        round_extracts,
        consensus_reached,
        consensus_round,
    )
    verdict_prompt = _settings_prompt(
        settings, "advisor_verdict_prompt", ADVISOR_VERDICT_PROMPT
    ).format(
        question=safe_question,
        transcript=transcript_text,
        debate_arc=debate_arc,
    )

    review_score_report = build_score_report(personas_list, all_rounds[-1]['responses'] if all_rounds else [])
    review_score_text = score_markdown(review_score_report)
    if review_score_report:
        verdict_prompt += '\n\n【程序计算的稿面评分，最终会自动附表】\n' + review_score_text
        verdict_prompt += '\n只分析意见与证据，不重新计算或另报总分。评分不等于意见正确，也不是CONSENSUS_SCORE。'

    if tiebreaker_result and tiebreaker_result.get("content"):
        verdict_prompt += f"\n\nTiebreaker ruling:\n{tiebreaker_result['content']}"
    if review_panel:
        final_responses = all_rounds[-1]['responses'] if all_rounds else []
        returned_names = [r['persona_name'] for r in final_responses if r.get('content') and not r.get('error')]
        absent_names = [p.name for p in personas_list if p.name not in returned_names]
        verdict_prompt += '\n【实际返回范围】已收到：' + '、'.join(returned_names) + '；未取得结果：' + ('、'.join(absent_names) or '无')
        verdict_prompt += '。只综合实际收到的意见；缺团不代表同意，不假称全体已审。评分引文匹配不证明判断正确，须复核确定问题与扣分理由是否被全文推翻。'

    if review_panel and not returned_names:
        verdict_data = {'model':verdict_model, 'content':None,
                        'error':'所有评审团均未取得结果，未生成主编汇总。请检查接口连接与返回的失败原因。'}
    else:
        verdict_data = await _query_neutral(
            verdict_model,
            apply_response_language(verdict_prompt, settings.response_language),
            conversation_id=conversation_id,
            **({"system_prompt": chair.system_prompt} if chair else {}),
        )
    if chair:
        verdict_data["persona_id"] = chair.id
        verdict_data["persona_name"] = chair.name
    if review_score_report:
        verdict_data['review_score_report'] = review_score_report
        if not verdict_data.get('error'):
            verdict_data['content'] = combine_verdict(verdict_data.get('content'), review_score_report)

    yield {"type": "advisor_verdict", "data": verdict_data}

    yield {
        "type": "advisor_complete",
        "data": {
            "rounds": all_rounds,
            "round_policy": round_policy,
            "consensus_reached": consensus_reached,
            "consensus_round": consensus_round,
            "round_extracts": round_extracts,
            "tiebreaker": tiebreaker_result,
            "verdict": verdict_data,
            "personas": personas_serialized,
            "cost_report": build_advisor_cost_report(
                cost_rounds,
                verdict_data,
                tiebreaker_result,
                round_extracts,
            ),
        },
    }
