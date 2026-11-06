# H3-2 Structured Error Recovery (deterministic probe)

- model: recovery-probe (acts only on structured error fields)
- note: Deterministic information-channel comparison, not real-model quality. Real-model recovery is deferred to H3-6.

| Case | on: recovered | off: recovered | on tools | off tools |
| --- | --- | --- | ---: | ---: |
| timeout_once | True | False | 2 | 1 |
| not_found | True | False | 1 | 1 |
| invalid_arguments | True | False | 1 | 1 |
| dependency_sticky | True | False | 2 | 1 |
| policy_rejection | True | False | 1 | 1 |
- on: recovery_rate=1.0, executor_calls=0
- off: recovery_rate=0.0, executor_calls=0
