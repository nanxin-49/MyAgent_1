"""Coordinate action recovery and idempotent checkpoint resume receipts."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from actions.models import ActionResult, ActionStatus
from actions.service import ActionService
from core.checkpoint import ActionCheckpoint, CheckpointService

logger = logging.getLogger(__name__)


@dataclass
class ResumeOutcome:
    checkpoint: ActionCheckpoint
    status: str
    response: str
    action_results: list[ActionResult] = field(default_factory=list)
    memory_write_status: str = "not_attempted"
    already_resumed: bool = False


def checkpoint_receipt(results: list[ActionResult]) -> str:
    lines: list[str] = []
    for result in results:
        action = result.action
        kind = ("退款" if action is not None
                and action.action_type.value == "refund" else "取消订单")
        action_id = result.action_id or (action.action_id if action else "未生成")
        if result.status is ActionStatus.COMPLETED:
            lines.append(f"演示业务后端中的{kind}动作已完成。动作编号：{action_id}。")
        elif result.status is ActionStatus.AWAITING_APPROVAL:
            lines.append(f"{kind}请求已提交，正在等待审批；尚未执行。动作编号：{action_id}。")
        elif result.status is ActionStatus.REJECTED:
            lines.append(f"{kind}请求已被拒绝，未执行。原因代码："
                         f"{result.error_code or 'unknown'}。动作编号：{action_id}。")
        elif result.status is ActionStatus.FAILED:
            lines.append(f"{kind}请求处理失败，不能视为已执行。错误代码："
                         f"{result.error_code or 'unknown'}。动作编号：{action_id}。")
        else:
            lines.append(f"{kind}动作当前状态：{result.status.value}。动作编号：{action_id}。")
    if not lines:
        return "没有可汇报的状态变更动作。"
    if len(lines) == 1:
        return lines[0]
    return ("本次共观察到 %d 个状态变更动作：\n" % len(lines)
            + "\n".join(f"- {line}" for line in lines))


class CheckpointResumer:
    """Resume a checkpoint through the existing ActionService and report once."""

    def __init__(self, checkpoints: CheckpointService, actions: ActionService,
                 memory: Any | None = None) -> None:
        self._checkpoints = checkpoints
        self._actions = actions
        self._memory = memory

    async def resume(self, request_id: str, *, user_id: str,
                     principal: Any | None) -> ResumeOutcome | None:
        checkpoint = self._checkpoints.get(request_id)
        if checkpoint is None or checkpoint.user_id != user_id:
            return None

        results: list[ActionResult] = []
        for item in checkpoint.actions:
            current = self._actions.get(
                item.action_id, user_id=user_id, principal=principal)
            if current.action is not None and current.status in {
                ActionStatus.APPROVED,
                ActionStatus.EXECUTING,
            }:
                current = self._actions.resume(
                    action_id=item.action_id,
                    user_id=user_id,
                    principal=principal,
                    request_id=request_id,
                )
            results.append(current)
            if current.action_id is not None:
                self._checkpoints.update_for_action(
                    item.action_id, current.status.value, current.error_code)

        checkpoint = self._checkpoints.get(request_id) or checkpoint
        statuses = {result.status for result in results}
        if statuses & {ActionStatus.PENDING, ActionStatus.AWAITING_APPROVAL}:
            return ResumeOutcome(
                checkpoint=checkpoint,
                status="awaiting_approval",
                response="仍有动作等待审批；批准后再调用检查点恢复。",
                action_results=results,
                memory_write_status="not_attempted",
            )
        if statuses & {ActionStatus.APPROVED, ActionStatus.EXECUTING}:
            return ResumeOutcome(
                checkpoint=checkpoint,
                status="executing",
                response="动作仍在执行或执行状态未知，不能确认完成。",
                action_results=results,
                memory_write_status="not_attempted",
            )

        receipt = checkpoint_receipt(results)
        if checkpoint.resumed_at is not None:
            return ResumeOutcome(
                checkpoint=checkpoint,
                status=checkpoint.status.value,
                response=receipt,
                action_results=results,
                memory_write_status="already_resumed",
                already_resumed=True,
            )

        memory_status = "not_available"
        if self._memory is not None:
            try:
                from memory.conversation_memory import MsgRole
                metadata = {
                    "source": "checkpoint_resume",
                    "request_id": request_id,
                    "checkpoint_status": checkpoint.status.value,
                }
                writer = getattr(self._memory, "add_message_once", None)
                if callable(writer):
                    appended = await writer(
                        user_id, checkpoint.conv_id, MsgRole.ASSISTANT, receipt,
                        metadata=metadata,
                        idempotency_key=f"checkpoint_resume:{request_id}",
                    )
                    memory_status = "completed" if appended else "already_written"
                else:
                    await self._memory.add_message(
                        user_id, checkpoint.conv_id, MsgRole.ASSISTANT, receipt,
                        metadata=metadata)
                    memory_status = "completed"
                checkpoint = self._checkpoints.mark_resumed(request_id) or checkpoint
            except Exception:
                memory_status = "failed"
                logger.warning(
                    "checkpoint_resume_memory_failed request_id=%s", request_id)

        return ResumeOutcome(
            checkpoint=checkpoint,
            status=checkpoint.status.value,
            response=receipt,
            action_results=results,
            memory_write_status=memory_status,
        )


__all__ = ["CheckpointResumer", "ResumeOutcome", "checkpoint_receipt"]
