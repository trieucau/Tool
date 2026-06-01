"""
translator.py — Fast Vietnamese translation with minimal API calls.

Primary path: ONE JSON request for the whole transcript (when under size limit).
Fallback: sequential large groups (no parallel hammering on rate limits).
Retry: one combined batch for leftovers; Groq first if configured.
"""

import json
import time
import copy
import re
import os
from typing import List, Optional, Callable, Dict, Tuple, Any
from app.utils import get_logger
from app.config import config

logger = get_logger(__name__)

PHASE1_WORKERS = int(os.getenv("TRANSLATE_WORKERS", "1"))
PHASE2_WORKERS = int(os.getenv("TRANSLATE_RETRY_WORKERS", "2"))
GROUP_MAX_CHARS = int(os.getenv("TRANSLATE_GROUP_MAX_CHARS", "4500"))
GROUP_MAX_SEGMENTS = int(os.getenv("TRANSLATE_GROUP_MAX_SEGMENTS", "40"))
FULL_DOC_MAX_CHARS = int(os.getenv("TRANSLATE_FULL_DOC_MAX_CHARS", "24000"))
MINI_CHUNK_SIZE = int(os.getenv("TRANSLATE_MINI_CHUNK", "20"))

_SYSTEM_PROMPT = """Bạn là một Chuyên gia Bản địa hóa (Localization Expert) và Biên kịch Lồng tiếng cấp cao tại Việt Nam.

MỤC TIÊU TỐI THƯỢNG:
Bản dịch phải đạt mức 10/10 về độ TỰ NHIÊN - tức là người nghe tin rằng câu này do người Việt bản xứ tự nghĩ ra và nói, chứ không phải một sản phẩm dịch thuật. Áp dụng kỹ thuật "Phóng tác" (Transcreation): Dịch Ý chứ không Dịch TỪ.

QUY TRÌNH TƯ DUY NGẦM:
1. Đọc hiểu nghĩa đen và sắc thái (vui, buồn, kịch tính, trang trọng...).
2. Đập bỏ hoàn toàn cấu trúc ngữ pháp gốc (Subject + Verb + Object của ngoại ngữ).
3. Tư duy như người Việt Nam: "Trong hoàn cảnh này, người Việt Nam sẽ nói câu gì?"
4. Chỉnh sửa nhịp điệu: Tối ưu cho AI Voice (TTS) hoặc diễn viên lồng tiếng (nhịp điệu trôi chảy, dễ ngắt nghỉ).

NHỮNG "TỬ HUYỆT" CẦN TRÁNH ĐỂ KHÔNG BỊ "DỊCH MÁY":
- BỆNH "BỊ ĐỘNG": Thay vì "Được tạo ra bởi X", dùng "Do X tạo ra". Thay vì "bị ảnh hưởng", có thể dùng "chịu tác động".
- BỆNH DƯ THỪA TỪ: Xóa bỏ triệt để các cụm vô nghĩa ở đầu câu: "Điều này...", "Việc đó...", "Đó là lý do tại sao...".
- BỆNH SỞ HỮU: Lược bỏ tối đa chữ "của" nếu không làm mất nghĩa (VD: "Kế hoạch của chúng tôi" -> "Kế hoạch chúng tôi").
- BỆNH ĐẠI TỪ: Không dịch cứng nhắc "Tôi/Bạn". Tự linh hoạt xưng hô dựa theo ngữ cảnh (Ta/Mình/Mọi người/Anh/Em...).
- BỆNH TỪ GHÉP ÉP BUỘC: Nếu từ chuyên ngành không có nghĩa tiếng Việt chuẩn xác và gọn gàng, hãy giữ nguyên tiếng Anh.
- SỐ LIỆU & ĐƠN VỊ: Chuyển về cách nói quen thuộc (VD: "10 tỷ đô", "5 chục ngàn", "20 phần trăm").

VÍ DỤ "LỘT XÁC" BẢN DỊCH:
❌ Gốc: "There are many things that you need to consider before making a decision."
❌ Dịch máy (4/10): "Có nhiều điều mà bạn cần xem xét trước khi đưa ra một quyết định."
✅ Đạt chuẩn (10/10): "Bạn phải cân nhắc rất nhiều thứ trước khi chốt hạ."

❌ Gốc: "It is highly recommended that users update their systems to the latest version to prevent security vulnerabilities."
❌ Dịch máy (4/10): "Nó được khuyến nghị cao rằng người dùng cập nhật hệ thống của họ lên phiên bản mới nhất để ngăn chặn các lỗ hổng bảo mật."
✅ Đạt chuẩn (10/10): "Người dùng nên cập nhật hệ thống ngay để tránh nguy cơ bảo mật."

❌ Gốc: "She broke into tears when she heard the news about her dog."
❌ Dịch máy (4/10): "Cô ấy đã vỡ oà trong nước mắt khi cô ấy nghe tin tức về con chó của cô ấy."
✅ Đạt chuẩn (10/10): "Cô òa khóc khi hay tin cún cưng gặp chuyện."

RÀNG BUỘC ĐẦU RA (TỐI QUAN TRỌNG):
1. ĐỊNH DẠNG JSON TUYỆT ĐỐI: Chỉ xuất một khối JSON duy nhất hợp lệ, KHÔNG markdown (bỏ ```json), KHÔNG giải thích.
2. BẢO TOÀN KEY: Giữ nguyên 100% các key ("0", "1", "2"...).
3. CHỈ DỊCH VALUE: Chỉ thay thế phần value bằng câu tiếng Việt đã tối ưu."""

_SINGLE_SYSTEM_PROMPT = """Bạn là Chuyên gia Bản địa hóa (Localization) và Biên kịch Lồng tiếng cấp cao.

Nguyên tắc dịch 10/10:
- "Phóng tác" (Transcreation) chứ không dịch từng từ. 
- Xóa bỏ hoàn toàn ngữ pháp ngoại ngữ. Dùng văn phong người Việt Nam nói chuyện hàng ngày.
- Không lạm dụng "của", "được/bị", "những/các".
- Tránh xa "Điều này", "Việc đó" ở đầu câu.
- Tối ưu câu chữ ngắn gọn, ngắt nhịp dễ dàng cho đọc thành tiếng (Voice-over/TTS).

Ví dụ: 
- "You need to understand this concept" -> "Bạn phải nắm rõ khái niệm này" (thay vì "Bạn cần hiểu khái niệm này").
- "The results were surprisingly good" -> "Kết quả tốt ngoài sức tưởng tượng" (thay vì "Các kết quả thì tốt một cách đáng ngạc nhiên").

Quy tắc:
Chỉ trả về trực tiếp đoạn văn bản tiếng Việt cuối cùng. Không giải thích, không thêm thắt nội dung ngoài bản dịch."""


class TranslationError(Exception):
    """Raised when translation cannot reach required Vietnamese coverage."""


def _build_client():
    try:
        from openai import OpenAI
    except ImportError:
        return None
    if not config.api.openai_api_key:
        return None
    return OpenAI(
        api_key=config.api.openai_api_key,
        base_url=config.api.openai_base_url or None,
    )


def _build_groq_client():
    try:
        from openai import OpenAI
    except ImportError:
        return None
    if not config.api.groq_api_key:
        return None
    return OpenAI(
        api_key=config.api.groq_api_key,
        base_url="https://api.groq.com/openai/v1",
    )


def _translation_clients() -> List[Tuple[Any, str, str]]:
    """Ordered list of (client, model, label). Prefer Groq when configured (higher limits)."""
    clients: List[Tuple[Any, str, str]] = []
    groq = _build_groq_client()
    if groq:
        clients.append((
            groq,
            os.getenv("GROQ_TRANSLATE_MODEL", "llama-3.3-70b-versatile"),
            "Groq",
        ))
    primary = _build_client()
    if primary:
        clients.append((primary, config.api.openai_model, "Primary"))
    return clients


def _is_vietnamese(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    vi_pattern = re.compile(
        r'[àáâãèéêìíòóôõùúýăđơư'
        r'ạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ'
        r'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐƠƯ'
        r'ẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ]'
    )
    vi_chars = len(vi_pattern.findall(stripped))
    if vi_chars == 0:
        letter_count = sum(1 for c in stripped if c.isalpha())
        return letter_count <= 2
    return vi_chars >= max(1, len(stripped) / 25)


def _looks_untranslated(text: str) -> bool:
    return not _is_vietnamese(text)


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg


def _split_translation_proportionally(parts: List[str], translated: str) -> List[str]:
    if len(parts) == 1:
        return [translated.strip()]
    words = translated.split()
    if not words:
        return parts
    weights = [max(1, len(p)) for p in parts]
    total_w = sum(weights)
    out: List[str] = []
    pos = 0
    for i, w in enumerate(weights):
        if i == len(weights) - 1:
            chunk_words = words[pos:]
        else:
            n = max(1, round(len(words) * w / total_w))
            chunk_words = words[pos : pos + n]
            pos += n
        out.append(" ".join(chunk_words).strip() or parts[i])
    return out


def _apply_payload(
    translated_segments: list,
    indices: List[int],
    payload: Dict[str, str],
    translated_data: dict,
) -> None:
    for idx in indices:
        key = str(idx)
        if key in translated_data and str(translated_data[key]).strip():
            translated_segments[idx].text = str(translated_data[key]).strip()

    missing = [i for i in indices if _looks_untranslated(translated_segments[i].text)]
    if not missing:
        return

    originals = [payload[str(i)] for i in missing]
    combined = " ".join(
        str(translated_data.get(str(i), "")).strip() for i in missing
    ).strip()
    if not combined:
        return
    parts = _split_translation_proportionally(originals, combined) if len(missing) > 1 else [combined]
    for i, seg_idx in enumerate(missing):
        if i < len(parts) and parts[i]:
            translated_segments[seg_idx].text = parts[i]


def _translate_chunk(
    client,
    payload: dict,
    label: str,
    model: Optional[str] = None,
) -> dict:
    model = model or config.api.openai_model
    user_prompt = (
        "Dịch các đoạn sau sang tiếng Việt. "
        "Giữ nguyên key JSON (số thứ tự segment):\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    last_err = None
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            data = json.loads(raw)
            if isinstance(data, dict) and data:
                return data
            raise ValueError(f"Empty response: {raw[:80]}")
        except Exception as e:
            last_err = e
            if _is_rate_limit_error(e) or _quota_exhausted(e):
                logger.warning(f"{label}: rate limit — skipping further API retries.")
                break
            wait = 2 ** (attempt + 1)
            logger.warning(f"{label} attempt {attempt + 1}: {e}. Retry in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"{label} failed: {last_err}")


def _quota_exhausted(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "per-day" in msg or "remaining': '0'" in msg or "remaining\": \"0\"" in msg


def _translate_with_any_client(
    clients: List[Tuple[Any, str, str]],
    payload: Dict[str, str],
    label: str,
) -> dict:
    last_err = None
    for client, model, name in clients:
        try:
            return _translate_chunk(client, payload, f"{label} ({name})", model=model)
        except Exception as e:
            last_err = e
            logger.warning(f"{label} via {name} failed: {e}")
            if _quota_exhausted(e):
                break
            if _is_rate_limit_error(e):
                time.sleep(2)
    raise RuntimeError(f"{label} all providers failed: {last_err}")


def _offline_translate_indices(
    original_segments: list,
    translated_segments: list,
    indices: List[int],
) -> int:
    """Free fallback when LLM quota is exhausted — keeps 100% Vietnamese output."""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        logger.error("deep-translator not installed. Run: pip install deep-translator")
        return 0

    translator = GoogleTranslator(source="auto", target="vi")
    ok = 0
    for idx in indices:
        text = original_segments[idx].text.strip()
        if not text:
            continue
        try:
            translated_segments[idx].text = translator.translate(text)
            ok += 1
        except Exception as e:
            logger.warning(f"Offline translate segment {idx} failed: {e}")
    logger.info(f"[TRANSLATE] Offline fallback translated {ok}/{len(indices)} segments")
    return ok


def _build_payload_for_indices(segments: list, indices: List[int]) -> Dict[str, str]:
    return {str(i): segments[i].text for i in indices if segments[i].text.strip()}


def _indices_needing_translation(segments: list) -> List[int]:
    return [
        i for i, s in enumerate(segments)
        if s.text.strip() and _looks_untranslated(s.text)
    ]


def _build_translation_groups(segments: list, indices: List[int]) -> List[List[int]]:
    groups: List[List[int]] = []
    current: List[int] = []
    chars = 0
    for idx in indices:
        tlen = len(segments[idx].text)
        if current and (len(current) >= GROUP_MAX_SEGMENTS or chars + tlen > GROUP_MAX_CHARS):
            groups.append(current)
            current = []
            chars = 0
        current.append(idx)
        chars += tlen
    if current:
        groups.append(current)
    return groups


def batch_translate_segments(
    segments: list,
    progress_callback: Optional[Callable] = None,
) -> list:
    clients = _translation_clients()
    if not clients:
        logger.warning("No translation API configured (OPENAI_API_KEY or GROQ_API_KEY).")
        return segments

    translated_segments = copy.deepcopy(segments)
    original_segments = segments
    total = len(segments)

    need_indices = _indices_needing_translation(segments)
    if not need_indices:
        logger.info("[TRANSLATE] All segments already Vietnamese.")
        return translated_segments

    total_chars = sum(len(segments[i].text) for i in need_indices)
    logger.info(
        f"[TRANSLATE] {len(need_indices)}/{total} segments, {total_chars} chars "
        f"| providers={[c[2] for c in clients]}"
    )

    api_rate_limited = False
    use_offline_first = os.getenv("TRANSLATE_OFFLINE_FIRST", "false").lower() == "true"

    if use_offline_first:
        if progress_callback:
            progress_callback(0.45, "Dịch offline (nhanh, không tốn quota API)...")
        _offline_translate_indices(original_segments, translated_segments, need_indices)
        need_indices = _indices_needing_translation(translated_segments)
        if not need_indices:
            logger.info("[TRANSLATE] Offline-first completed all segments.")
            return translated_segments

    # ── Path A: single API call for entire transcript ─────────────────────────
    if total_chars <= FULL_DOC_MAX_CHARS and need_indices:
        payload = _build_payload_for_indices(segments, need_indices)
        if progress_callback:
            progress_callback(0.45, "Dịch toàn bộ phụ đề (1 lần gọi API)...")
        try:
            data = _translate_with_any_client(clients, payload, "Full-document")
            _apply_payload(translated_segments, need_indices, payload, data)
            logger.info("[TRANSLATE] Full-document translation applied.")
        except Exception as e:
            logger.warning(f"[TRANSLATE] Full-document failed: {e}")
            if _quota_exhausted(e) or _is_rate_limit_error(e):
                api_rate_limited = True

    # ── Path B: sequential groups (skip if quota dead) ─────────────────────────
    need_indices = _indices_needing_translation(translated_segments)
    if need_indices and not api_rate_limited:
        groups = _build_translation_groups(segments, need_indices)
        logger.info(f"[TRANSLATE] Sequential groups: {len(groups)}")
        for gnum, gindices in enumerate(groups, 1):
            if progress_callback:
                progress_callback(
                    0.48 + 0.10 * (gnum / max(len(groups), 1)),
                    f"Dịch nhóm {gnum}/{len(groups)}...",
                )
            payload = _build_payload_for_indices(segments, gindices)
            try:
                data = _translate_with_any_client(clients, payload, f"Group-{gnum}")
                _apply_payload(translated_segments, gindices, payload, data)
            except Exception as e:
                logger.error(f"Group {gnum} failed: {e}")
                if _quota_exhausted(e) or _is_rate_limit_error(e):
                    api_rate_limited = True
                    break

    # ── Path C: one final LLM batch ───────────────────────────────────────────
    need_indices = _indices_needing_translation(translated_segments)
    if need_indices and not api_rate_limited:
        if progress_callback:
            progress_callback(0.58, "Dịch lại đoạn còn sót (1 batch)...")
        logger.info(f"[TRANSLATE] Final LLM batch: {len(need_indices)} segments")
        payload = _build_payload_for_indices(original_segments, need_indices)
        try:
            data = _translate_with_any_client(clients, payload, "Final-batch")
            _apply_payload(translated_segments, need_indices, payload, data)
        except Exception as e:
            logger.error(f"[TRANSLATE] Final batch failed: {e}")
            if _quota_exhausted(e) or _is_rate_limit_error(e):
                api_rate_limited = True

    # ── Path D: offline fallback (fast, no API quota) ─────────────────────────
    need_indices = _indices_needing_translation(translated_segments)
    if need_indices:
        if progress_callback:
            progress_callback(0.59, "Dịch dự phòng (Google Translate)...")
        _offline_translate_indices(original_segments, translated_segments, need_indices)

    still = _indices_needing_translation(translated_segments)
    logger.info(f"[TRANSLATE] Done: {total - len(still)}/{total} segments Vietnamese.")
    if still:
        logger.warning(
            f"[TRANSLATE] {len(still)} segment(s) still not Vietnamese. "
            "Check API quota — set GROQ_API_KEY or paid OPENAI_API_KEY."
        )
        if len(still) > total * 0.05:
            raise TranslationError(
                f"{len(still)}/{total} segments could not be translated to Vietnamese. "
                "API rate limit or quota exceeded. Add GROQ_API_KEY in .env or use a paid model."
            )

    return translated_segments


def translate_to_vietnamese(text: str) -> str:
    clients = _translation_clients()
    if not clients:
        return text
    payload = {"0": text}
    try:
        data = _translate_with_any_client(clients, payload, "block")
        return str(data.get("0", text)).strip() or text
    except Exception:
        return text
