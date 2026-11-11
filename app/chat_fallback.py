"""Free rule-based Kraken chat when the LLM API is unavailable.

Deterministic help and *verified* report summaries, not generated AI. Never
invent product specifications, supplier prices, quotations or recommendations.
Gemini integration remains in app.ai/ai_stream and can be re-enabled by env.
"""
from __future__ import annotations
import os
import re
from typing import Any

def active() -> bool:
    return os.getenv("CHAT_MODE", "auto").strip().lower() == "rules"

def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", message.casefold().replace("ё", "е")).strip(" !?.,;:—-")

def _has(message: str, *words: str) -> bool:
    return any(word in message for word in words)

def _greeting(message: str) -> bool:
    return bool(re.fullmatch(
        r"(?:привет(?:ик|ствую|ствуй|ули)?|здрасте|здравствуйте|здравствуй|"
        r"добрый (?:день|вечер|утро)|хай|хелло|hello|hi|"
        r"привет как дела|как дела|как ты|ку|йо|салют)(?:[\s!?.]*)",
        message, re.I))

def _supplier(result:dict[str,Any], message:str) -> dict[str,Any] | None:
    suppliers=result.get("suppliers") or []
    return next((s for s in suppliers if s.get("name") and
                 s["name"].casefold() in message.casefold()), None)

def _report(result: dict[str,Any]) -> str:
    suppliers = result.get("suppliers") or []
    requirements = result.get("requirements") or []
    if not suppliers:
        return "В этом анализе пока нет обработанных коммерческих предложений."
    lines=[f"В текущем анализе: {len(suppliers)} КП и {len(requirements)} распознанных требований."]
    summary=result.get("decision_summary") or {}
    if summary:
        lines.append("Подтверждено подходящих: {eligible}; с нарушениями: {rejected}; требуют уточнения: {needs_review}.".format(
            eligible=summary.get("eligible",0), rejected=summary.get("rejected",0),
            needs_review=summary.get("needs_review",0)))
    for supplier in suppliers[:10]:
        name=supplier.get("name","КП")
        fail=supplier.get("mandatory_failed", supplier.get("failed",0))
        unknown=supplier.get("mandatory_unknown", supplier.get("unknown",0))
        checked=supplier.get("checks") or []
        if fail: verdict="не подходит по распознанным обязательным требованиям"
        elif unknown or not checked: verdict="нужно уточнение"
        else: verdict="обязательные распознанные требования подтверждены"
        lines.append(f"• {name}: {verdict} (нарушений: {fail}, неясных условий: {unknown}).")
    recommended=result.get("recommended")
    if recommended:
        lines.append(f"Предварительно первое место в расчётном рейтинге: {recommended}. Это не окончательное решение о закупке.")
    lines.append("Вывод относится только к распознанным требованиям. Проверьте первоисточники в разделе «Аналитика».")
    return "\n".join(lines)

def _problems(result:dict[str,Any], supplier:dict[str,Any]|None=None) -> str:
    suppliers=[supplier] if supplier else result.get("suppliers",[])
    entries=[]
    for s in suppliers:
        for c in (s.get("checks") or []):
            if c.get("status")=="fail":
                req=str(c.get("requirement_source") or c.get("required") or "условие не указано").strip()[:165]
                actual=str(c.get("offer_source") or c.get("actual") or "нет подтверждения").strip()[:165]
                entries.append(f"• {s.get('name','КП')} — {c.get('parameter','параметр')}: ТЗ «{req}», КП «{actual}».")
    if not entries:
        return ("Подтверждённых расхождений среди распознанных проверок не найдено. "
                "Это не доказывает полное соответствие: проверьте неизвестные и пропущенные требования.")
    extra = "" if len(entries)<=8 else f"\nИ ещё {len(entries)-8} расхождений — подробности в «Аналитике»."
    return "Подтверждённые расхождения:\n"+"\n".join(entries[:8])+extra

def _unknown(result:dict[str,Any]) -> str:
    rows=[]
    for s in result.get("suppliers",[]):
        missing=[str(c.get("parameter") or "параметр") for c in s.get("checks",[]) if c.get("status")=="unknown"]
        if missing:
            rows.append(f"• {s.get('name','КП')}: {', '.join(missing[:6])}" +
                        (f" и ещё {len(missing)-6}" if len(missing)>6 else ""))
    if not rows:
        return "Среди распознанных проверок нет статуса UNKNOWN. Это не гарантирует, что все требования ТЗ извлечены."
    return "Требуется уточнение по следующим характеристикам:\n"+"\n".join(rows[:10])

def _prices(result:dict[str,Any]) -> str:
    lines=[]
    for s in result.get("suppliers",[])[:10]:
        facts=s.get("facts") or []
        price=next((f.get("value") for f in facts if f.get("key")=="price" and
                    isinstance(f.get("value"),(int,float)) and f.get("value")>0),None)
        if price is None: lines.append(f"• {s.get('name','КП')}: цена не подтверждена.")
        else: lines.append(f"• {s.get('name','КП')}: {price:,.2f} ₽.".replace(","," "))
    return "Цены из распознанных данных:\n"+"\n".join(lines)+\
        "\nЕсли цена не найдена, это не означает, что её нет в исходном документе."

HELLO=("Привет! Я Kraken — помощник по сравнению коммерческих предложений. "
       "Могу объяснить процесс закупки, подсказать, как загрузить ТЗ и КП, "
       "и разобрать результаты уже выполненного анализа. С чего начнём?")
HOW_COMPARE=(
    "Чтобы правильно сравнить коммерческие предложения:\n"
    "1. Выпишите все требования ТЗ и разделите их на обязательные и дополнительные.\n"
    "2. Приведите характеристики к общим единицам: ГБ, рубли, дни и т. д.\n"
    "3. Для каждого КП проверьте каждый обязательный пункт: соответствует, не соответствует или данных недостаточно.\n"
    "4. Исключите предложения с подтверждённым нарушением обязательных условий; неизвестные параметры отправьте на уточнение.\n"
    "5. Среди допустимых КП сравните полную цену, срок поставки, гарантию и другие критерии с весами из ТЗ.\n"
    "6. Проверьте источники чисел и зафиксируйте причины выбора.\n\n"
    "Kraken автоматизирует распознанные проверки и показывает рейтинг, но перед реальной закупкой вывод нужно подтвердить по документам.")
FORMATS=("Откройте «Загрузить документы»: добавьте 1 ТЗ и от 1 до 10 КП. "
         "Поддерживаются PDF, DOCX, XLSX и TXT (UTF-8), до 5 МиБ на файл. "
         "КП можно выбирать за несколько раз и удалять из списка до отправки. "
         "После загрузки откройте «Аналитику» для сравнения.")
RANKING=("Kraken сначала проверяет обязательные требования и не рекомендует КП с подтверждённым нарушением или неизвестными обязательными параметрами. "
         "После этого подходящие предложения сравниваются по весам ТЗ, если они распознаны, "
         "или по общим весам по умолчанию: соответствие 60%, цена 25%, срок поставки 15%. "
         "Если части данных нет, рейтинг предварительный. Равенство баллов не означает победу одного из поставщиков.")
E5=("E5 Small — энкодер: он превращает текст в векторы. "
    "По косинусному сходству система ищет фрагменты КП, связанные с требованиями ТЗ. "
    "Это поиск доказательств, а не проверка выполнения: 8 ГБ и 16 ГБ могут иметь высокое текстовое сходство, "
    "но не соответствовать одному и тому же условию. Числа проверяются отдельно.")
LIMITATIONS=("Сейчас работает бесплатный справочный режим, без генеративной модели. "
             "Я могу отвечать на типовые вопросы и пересказывать подтверждённые результаты анализа, "
             "но не могу свободно рассуждать обо всём или придумывать сведения из документов. "
             "Gemini сохранён в коде и может быть включён позже.")

def respond(message:str, result:dict[str,Any]|None=None,
            evidence:list[dict[str,Any]]|None=None)->str:
    q=_normalize(message)
    if not q:
        return "Напишите вопрос. Например: «Как сравнить коммерческие предложения?»"
    if _greeting(q):
        return HELLO
    if _has(q,"спасибо","благодарю","спс"):
        return "Пожалуйста! Могу помочь с загрузкой документов, объяснить рейтинг или разобрать найденные расхождения."
    if _has(q,"пока","до свидания","увидимся"):
        return "До встречи! Когда понадобится проверить КП, загружайте ТЗ и предложения."
    if _has(q,"что ты умеешь","что умеешь","как пользоваться","как работает сайт","инструкция","помощь","помоги разобраться"):
        return ("Я помогаю сравнивать коммерческие предложения с ТЗ. "+FORMATS+
                "\n\nМожно спросить: «Как сравнить КП?», «Какие нарушения?», «Почему первое место?» или «Какие цены указаны?».")
    if _has(q,"как правильно срав","как сравни","как проверить кп","как оценить предложение","какие критерии","как выбрать поставщика"):
        return HOW_COMPARE
    if _has(q,"как загруз","какие файлы","формат","pdf","docx","xlsx","txt","сколько кп","10 кп","лимит"):
        return FORMATS
    if _has(q,"энкодер","эмбеддинг","косинус","e5","вектор"):
        return E5
    if _has(q,"как ранж","как работает ранж","ранжирование","как рассчитыва","как считают баллы","какие веса","как выбрать победителя"):
        return RANKING
    if _has(q,"gemini","нейросет","без аи","без ии","бесплатн","что за модель"):
        return LIMITATIONS
    if result is not None:
        supplier=_supplier(result,message)
        if _has(q,"цен","стоим","рубл","сколько стоит","дешев"):
            return _prices(result)
        if _has(q,"неизвест","не найден","нет данных","не указан","не хватает","уточн"):
            return _unknown(result)
        if _has(q,"ошибк","наруш","расхожд","не соответств","не подход","проблем"):
            return _problems(result,supplier)
        if _has(q,"кто побед","кто лучше","какое лучше","лучшее","первое место","почему выб","рекоменд","рейтинг","ранжир","итог","результат","сравни"):
            return _report(result)+("\n\n"+RANKING if _has(q,"почему","критери") else "")
        if supplier is not None:
            return _report({"suppliers":[supplier], "requirements":result.get("requirements") or []})
        if _has(q,"гарант","достав","срок","процессор","памят","ssd","экран"):
            # We cannot infer per-attribute truth from raw LLM-like guesses.
            matches=[]
            for s in result.get("suppliers",[]):
                for c in s.get("checks",[]):
                    p=str(c.get("parameter") or "").casefold()
                    if any(token in p for token in re.findall(r"[а-яa-z0-9]{3,}",q)):
                        matches.append(f"• {s.get('name','КП')}: {p} — {c.get('status','unknown')}; "+
                                       f"ТЗ: {str(c.get('requirement_source') or c.get('required') or '—')[:130]}; "+
                                       f"КП: {str(c.get('offer_source') or c.get('actual') or '—')[:130]}")
            if matches:return "Проверенные характеристики:\n"+"\n".join(matches[:8])
        return ("Вопрос не входит в набор готовых ответов. В текущем анализе доступны "
                "сводка, цены, нарушения и неизвестные требования. Спросите, например, "
                "«Какие нарушения?» или «Кто на первом месте?». "
                "Свободная генерация временно отключена.")
    return ("Сейчас работаю без генеративной нейросети, но могу помочь с закупками. "
            "Спросите «Как правильно сравнивать коммерческие предложения?», "
            "«Как загрузить файлы?» или «Как работает ранжирование?». "
            "Чтобы обсудить конкретные КП, сначала загрузите ТЗ и предложения.")
