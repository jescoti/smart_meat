# Orchestration Reflections: 16-WU Parallel Agent Execution

Report from the orchestrated execution of the Smart Meat MVP — 16 work units across 6 phases using metaswarm's 4-phase loop (IMPLEMENT, VALIDATE, ADVERSARIAL REVIEW, COMMIT) with isolated git worktree agents.

## Execution Summary

- **16 work units** completed across 3 sessions (context compaction required 2 recovery cycles)
- **1,122 tests** (772 backend + 350 frontend), 100% coverage
- **176 files**, ~38,000 lines
- **Parallel execution** used for WU-2/3, WU-6/7, WU-11/12, and individual agent dispatches
- **3 context recoveries** via `.beads/` persistence (execution state, active plan, project context)

## What Worked Well

### 1. Worktree Isolation

Each agent ran in an isolated git worktree, preventing interference between parallel agents. This was essential for WU-11 (Reply Flow) and WU-12 (Full-Text Search) which both touched overlapping areas of the codebase.

### 2. Orchestrator-Level Validation

The orchestrator never trusted agent self-reports. After every agent completed, we ran full test suites independently in the main worktree. This caught issues the agents couldn't see (router merge conflicts, missing coverage includes).

### 3. Incremental Commits per WU

Each work unit was committed separately with a descriptive message. This provides clean `git bisect` capability and makes it easy to review each feature independently via `git show <hash>`.

### 4. Context Recovery via .beads/

When the conversation hit context limits (twice), the execution state persisted to `.beads/context/execution-state.md` allowed seamless recovery. The orchestrator picked up exactly where it left off without re-running review gates or re-validating completed work.

## Problems Encountered and Solutions

### Problem 1: Shared File Overwrites (High Impact)

**What happened**: Parallel agents each forked from the same base commit. When they completed, each agent's version of `router.py` only contained their own sub-router, overwriting the merged version from previous WUs.

**Affected files (every time)**:
- `backend/app/api/router.py` — router aggregation
- `backend/tests/conftest.py` — env var defaults for Settings singleton
- `frontend/vitest.config.ts` — coverage include patterns

**Solution applied**: After every agent merge, the orchestrator manually re-merged these three files. This was a recurring manual step for all 16 WUs.

**Recommendation**: The orchestration framework should support a "protected files" declaration in the work unit spec. These files would be excluded from agent worktree copies and instead patched incrementally by the orchestrator using a merge strategy (e.g., "append import + include_router call to router.py").

### Problem 2: Deeply Nested Worktree Paths

**What happened**: Agent worktrees nested inside agent worktrees created paths like:
```
.claude/worktrees/agent-a9697470/.claude/worktrees/agent-ad6d1a10/
  .claude/worktrees/agent-a6d71b12/.claude/worktrees/agent-a9d7365e/
    .claude/worktrees/agent-aa6f3883/.claude/worktrees/agent-a268519a/
```

These 6-level-deep paths were fragile and confusing. File copy commands became extremely long.

**Recommendation**: Worktree agents should always create their worktrees relative to the repo root, not nested inside parent worktrees. Alternatively, the framework should flatten worktree paths to a single `.claude/worktrees/` directory regardless of dispatch depth.

### Problem 3: Settings Singleton Import-Time Failure

**What happened**: Pydantic's `Settings()` loads all env vars at import time. When `backend/app/api/router.py` was imported during test collection, it triggered `Settings()` instantiation, which failed because test env vars weren't set yet.

**Solution**: Added `os.environ.setdefault()` calls at the top of `conftest.py` before any app imports.

**Recommendation**: Router factory functions should use lazy settings loading (dependency injection at request time, not module import time). This would decouple test collection from runtime configuration.

### Problem 4: Agent Dispatched to Wrong Branch

**What happened**: WU-4 was committed to branch `worktree-agent-a22337d9` instead of the main development branch `worktree-agent-a9697470`. This required re-committing the files on the correct branch.

**Recommendation**: The orchestrator should verify the target branch before and after agent dispatch. A post-merge check like `git log --oneline -1` on the target branch confirms the commit landed correctly.

### Problem 5: Context Compaction Mid-Execution

**What happened**: The conversation hit context limits twice during the 16-WU execution, requiring session continuation with a summary prompt.

**Impact**: Each recovery required re-reading key files and re-establishing the execution state. About 10-15 minutes of overhead per recovery.

**What helped**: The `.beads/context/execution-state.md` file tracked which WUs were complete, in progress, and pending. This made recovery deterministic rather than requiring the orchestrator to re-derive state from git history.

**Recommendation**: For executions larger than ~10 WUs, consider breaking into multiple PRs (one per phase) rather than one monolithic PR. This reduces context pressure and provides natural review boundaries.

## Metrics

| Metric | Value |
|---|---|
| Total work units | 16 |
| Parallel batches | 4 (WU-2/3, WU-6/7, WU-11/12, individual dispatches) |
| Shared file re-merges | ~12 (router.py, conftest.py, vitest.config.ts) |
| Context recoveries | 2 |
| Backend tests | 772 |
| Frontend tests | 350 |
| Total test count | 1,122 |
| Coverage | 100% (lines, branches, functions, statements) |
| Files changed | 176 |
| Lines added | ~38,000 |
| Backend source files | 35 |
| Frontend source files | 78 |

## Recommendations for the Framework

1. **Protected file declarations**: Allow work unit specs to declare files that should not be overwritten by agents. The orchestrator patches these files incrementally.

2. **Flat worktree paths**: Prevent worktree nesting. All agent worktrees should be siblings in a single directory.

3. **Post-merge branch verification**: Automatically verify commits land on the correct branch after agent merges.

4. **Lazy settings loading**: Recommend lazy dependency injection patterns in router factories to prevent import-time configuration failures.

5. **Phase-based PR boundaries**: For large executions (10+ WUs), recommend splitting into one PR per phase rather than a single monolithic PR.

6. **Shared file merge strategies**: Provide built-in merge strategies for common aggregation patterns (router includes, config arrays, re-exports).
