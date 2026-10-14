"""Minimal process-local demo handoff facts; no human dispatch or notifications."""
import hashlib
import re
import uuid
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict
from core.auth import Principal, customer_identity


class HandoffResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: Literal["not_required", "required", "requested", "created", "failed"] = "not_required"
    handoff_required: bool = False
    handoff_requested: bool = False
    handoff_created: bool = False
    handoff_failed: bool = False
    handoff_id: str | None = None
    reason_code: str | None = None
    error_code: str | None = None
    reused: bool = False
    simulated: bool = True


def explicit_handoff(message):
    """Conservative current-turn syntax, not output keywords or conversation history."""
    clauses = re.split(r"[，。！？,;；.!?\n]", message.lower())
    for clause in clauses:
        if re.search(r"不需要|不想|不要|不用|无需|别|do not|don't|no need", clause):
            continue
        match = re.search(r"(?:转|找|联系|需要|要求|想要|想)(?:接|一下|个|要)?(?:人工(?:客服)?|真人客服)|(?:talk to|transfer to|want) (?:a |an )?(?:human|agent)", clause)
        if match is None:
            continue
        prefix = clause[:match.start()]
        suffix = clause[match.end():].lstrip(' \t“”"\'‘’「」')
        # Interpret the matched action in its clause: reported completion and
        # questions about meaning/rules are not requests to create a record.
        # Do not reject question punctuation: "可以帮我转人工客服吗" is a request.
        if re.search(
            r"(?:是否|是不是|能否|算不算).*(?:说明|表示|代表|意味|等于|已|完成)"
            r"|(?:是否|是不是|有没有)(?:已(?:经)?)?(?:帮我|为我)?$"
            r"|(?:已(?:经)?|成功|完成)(?:帮我|为我)?$"
            r"|(?:写着|显示为?|记载为?|标记为?|提示)[“\"'「\s]*$"
            r"|(?:如何|怎么|何时|什么时候|什么情况|为什么)"
            r"|\b(?:how|when|why|what does)\b|\balready\s*$", prefix,
        ) or re.search(
            r"^(?:的)?(?:意思|含义|规则|流程|条件|状态|结果)"
            r"|^(?:是什么|是指|代表|意味|成功|完成|了吗|是否|是不是)"
            r"|^\s+(?:mean|means|work|status|rules|process)\b", suffix,
        ):
            continue
        return True
    return False


def allowed_reason(req, reason):
    if reason == "explicit_request":
        return explicit_handoff(req.message)
    # A current-turn opt-out overrides optional Agent escalation.
    if re.search(r"(?:不需要|不想|不要|不用|无需).{0,5}人工", req.message):
        return False
    if reason == "complex_complaint":
        return bool(re.search(r"订单|退款|售后|商品|物流", req.message) and
                    re.search(r"投诉|争议|多次.*(?:未|没|不)|反复.*(?:未|没|不)", req.message))
    if reason == "business_dependency_failure":
        return any(t.get("tool_name") in {"get_order", "get_shipment", "get_refund_status"}
                   and t.get("error_code") in {"dependency_failure", "service_unavailable", "timeout"}
                   for t in req.handoff_evidence)
    return False


def handoff_reply(result):
    if result.handoff_created:
        return f"已创建模拟人工交接记录。交接编号：{result.handoff_id}。这不代表真实客服已接单。"
    if result.handoff_failed:
        return f"人工交接创建失败，未完成转接。错误代码：{result.error_code}。请稍后重试。"
    return "本次未创建人工交接记录。"


class HandoffService:
    def __init__(self):
        self._lock = RLock()
        self._records = {}
        self._attempts = {}

    def _create_record(self, owner, subject, reason):
        return {"owner": owner, "requested_by": subject, "handoff_id": str(uuid.uuid4()),
                "status": "created", "reason_code": reason, "simulated": True,
                "summary": {"explicit_request": "用户请求人工协助",
                            "complex_complaint": "电商投诉需要人工核验",
                            "business_dependency_failure": "业务查询依赖故障需要人工核验"}[reason]}

    def request(self, req, reason):
        owner = customer_identity(req.principal, req.user_id)
        if not allowed_reason(req, reason):
            return HandoffResult(error_code="handoff_policy_rejected", reason_code="not_eligible")
        scope = (req.principal.subject_id, owner, req.conv_id, req.handoff_key or req.request_id)
        fingerprint = hashlib.sha256(req.message.encode("utf-8")).hexdigest()
        with self._lock:
            previous = self._attempts.get(scope)
            if previous:
                bound, receipt = previous
                if bound != fingerprint:
                    return HandoffResult(status="failed", handoff_required=True, handoff_failed=True,
                                         error_code="handoff_idempotency_conflict", reason_code=reason)
                return receipt.model_copy(update={"reused": True})
            try:
                record = self._create_record(owner, req.principal.subject_id, reason)
                self._records[record["handoff_id"]] = dict(record)
                result = HandoffResult(status="created", handoff_required=True, handoff_requested=True,
                    handoff_created=True, handoff_id=record["handoff_id"], reason_code=reason)
            except Exception:
                result = HandoffResult(status="failed", handoff_required=True, handoff_requested=True,
                    handoff_failed=True, reason_code=reason, error_code="handoff_service_unavailable")
            self._attempts[scope] = (fingerprint, result)
            return result

    def get(self, handoff_id, principal: Principal):
        owner = customer_identity(principal)
        with self._lock:
            record = self._records.get(handoff_id)
            return dict(record) if record and record["owner"] == owner else None
