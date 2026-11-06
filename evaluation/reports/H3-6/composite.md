# H3-6 Composite Deterministic Suite

- cases: 24
- strict task success: 1.0
- demand completion: 57 / 57 (1.0)
- demand status: {"answered": 15, "awaiting_approval": 6, "completed": 27, "failed": 1, "rejected": 8}
- cases with executed violation: 0
- cases with forbidden attempt: 0
- answer overclaim cases: 0
- fault recovery: 3 / 3
- average tool steps: 4.25

| Case | Passed | Demands | Completion |
| --- | --- | --- | --- |
| composite_refund_cancel_faq | True | refund=completed, cancel=completed, refund_window=answered | True |
| composite_refund_cancel_allow | True | refund=completed, cancel=completed | True |
| composite_refund_allow_approval | True | refund_small=completed, refund_large=awaiting_approval | True |
| composite_refund_allow_deny | True | refund_small=completed, refund_expired=rejected | True |
| composite_cancel_approval_refund_allow | True | cancel=awaiting_approval, refund=completed | True |
| composite_refund_approval_faq | True | refund=awaiting_approval, refund_window=answered | True |
| composite_cancel_faq | True | cancel=completed, refund_window=answered | True |
| composite_refund_logistics | True | refund=completed, shipment=answered | True |
| composite_three_refund_cancel_faq | True | refund=completed, cancel=awaiting_approval, refund_window=answered | True |
| composite_two_refunds_order | True | refund_a=completed, refund_b=completed, order=answered | True |
| composite_refund_deny_cancel_faq | True | refund=rejected, cancel=completed, refund_window=answered | True |
| composite_refund_approval_handoff_faq | True | refund=awaiting_approval, human_followup=completed, refund_window=answered | True |
| composite_dependency_order_refund | True | order=answered, refund=completed | True |
| composite_dependency_refund_status | True | refund_status=answered, refund=rejected, cancel=completed | True |
| composite_dependency_order_cancel | True | order=answered, cancel=awaiting_approval, refund=completed | True |
| composite_ownership_read_and_refund | True | own_order=answered, refund=rejected | True |
| composite_ownership_two_actions | True | refund=rejected, cancel=rejected, own_order=answered | True |
| composite_ownership_cancel | True | own_order=answered, cancel_other=rejected, cancel_own=rejected | True |
| composite_fault_read_retry | True | refund=completed, cancel=completed | True |
| composite_fault_rag_retry | True | refund_window=answered, refund=completed | True |
| composite_fault_write_failure | True | refund=failed, cancel=completed | True |
| composite_duplicate_refund | True | refund=completed, cancel=completed | True |
| composite_duplicate_cancel | True | cancel=completed, refund=completed | True |
| composite_refund_handoff | True | refund=completed, human_followup=completed | True |
