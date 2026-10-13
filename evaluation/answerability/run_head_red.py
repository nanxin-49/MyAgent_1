"""Re-run corrected acceptance tests against the two ORIGINAL HEAD modules.

No filesystem rollback, service start, checkout, commit or push.
"""
import subprocess
import sys
import types

import pytest


def main():
    for name,path in [('agents.tools','agents/tools.py'),('agents.support_agent','agents/support_agent.py')]:
        original = subprocess.check_output(['git','show',f'HEAD:{path}']).decode('utf-8')
        module = types.ModuleType(name)
        module.__file__ = path
        module.__package__ = 'agents'
        sys.modules[name] = module
        exec(compile(original,path,'exec'),module.__dict__)
    return pytest.main(['-q','tests/test_answerability_boundary.py'])


if __name__=='__main__':
    raise SystemExit(main())
