# PR Review Guidelines

## Purpose
These guidelines ensure every pull request is properly reviewed before it's merged, so quality and consistency stay high across the project.

---

## Review Requirements
Every PR needs **3 approvals** before merging.

Reviewer composition must be one of the following:

| Combination | Allowed? |
|---|---|
| 1 Lead + 2 Member | ✅ |
| 2 Lead + 1 Member | ✅ |
| 3 Lead | ✅ |
| 3 Member | ❌ Not allowed |

**Rule of thumb:** at least 1 Lead reviewer must approve every PR.

---

## Review Checklist

### 1. PR Description & Setup
- [ ] PR description aligns with the task
- [ ] Planner task link is included and correct
- [ ] A new branch was created for the task (from `master`)
- [ ] Each task is submitted as its own separate PR

### 2. Files Changed
- [ ] Files are named correctly
- [ ] "Files changed" tab only shows the files required for this task
- [ ] No unrelated or previous-task files included

### 3. File Contents vs Task Requirements
- [ ] File contents are correct and complete
- [ ] Changes actually fulfill what the task/Planner ticket asked for
- [ ] No missing pieces, no leftover placeholder/test code

---

## Reviewing

- If something is wrong or missing, **Request changes** and leave a comment explaining what needs to be fixed
- If everything looks good, **Approve** the PR
