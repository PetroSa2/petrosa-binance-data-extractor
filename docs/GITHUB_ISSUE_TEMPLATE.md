# GitHub Issue Template

Use this template when creating new GitHub issues for the petrosa-binance-data-extractor service.

---

## 📋 Issue Type
- [ ] Bug
- [ ] Feature
- [ ] Technical Debt
- [ ] Testing
- [ ] Documentation
- [ ] Performance
- [ ] Security

## 🎯 Summary

[Provide a clear, concise summary of the issue in 1-2 sentences]

## 📊 Estimation

- **Size**: [XS/S/M/L/XL]
- **Priority**: [Low/Medium/High/Critical]
- **Estimate**: [X] minutes (Cursor implementation time)
- **Complexity**: [Low/Low-Medium/Medium/Medium-High/High]

### Size Guide
- **XS (Extra Small)**: < 30 minutes - Trivial changes, typo fixes, simple config updates
- **S (Small)**: 30-180 minutes - Single file changes, simple bug fixes, basic tests
- **M (Medium)**: 180-480 minutes - Multiple file changes, moderate features, refactoring
- **L (Large)**: 480-960 minutes - Complex features, architectural changes, extensive testing
- **XL (Extra Large)**: > 960 minutes - Major features, system redesigns, breaking changes

### Priority Guide
- **Low**: Can wait, nice to have, no business impact
- **Medium**: Should be done soon, minor impact on quality/performance
- **High**: Important for operations, user experience, or system stability
- **Critical**: Blocking issue, security vulnerability, production outage

## 🔍 Problem Statement

[Describe the problem in detail. What is broken? What is missing? Why does this need to be addressed?]

### Current Behavior
[What happens now?]

### Expected Behavior
[What should happen?]

### Root Cause (if known)
[Why is this happening?]

## 📝 Detailed Changes Required

### Option 1: [Approach Name]
[Describe the first possible solution]

**Pros**:
- [List advantages]

**Cons**:
- [List disadvantages]

### Option 2: [Approach Name] (if applicable)
[Describe alternative solution]

**Pros**:
- [List advantages]

**Cons**:
- [List disadvantages]

### Recommended Approach
[Which option to pursue and why]

## 🎯 Acceptance Criteria

- [ ] [Specific, testable criterion 1]
- [ ] [Specific, testable criterion 2]
- [ ] [Specific, testable criterion 3]
- [ ] All tests pass
- [ ] Linting passes
- [ ] No regression in functionality
- [ ] Documentation updated

## 🏗️ Implementation Plan

### Phase 1: [Phase Name]
1. [Step 1]
2. [Step 2]
3. [Step 3]

### Phase 2: [Phase Name] (if multi-phase)
1. [Step 1]
2. [Step 2]

## 📊 Impact Assessment

### Risk Level: [LOW/MEDIUM/HIGH/CRITICAL]

**Affected Components**:
- [Component 1]
- [Component 2]

**Breaking Changes**: [YES/NO]
- [If yes, describe what breaks]

**Benefits**:
- [Benefit 1]
- [Benefit 2]

**Risks**:
- [Risk 1]
- [Risk 2]

**Mitigation**:
- [How to mitigate risks]

## 📁 Files Affected

```
✏️  Modified:
├── [file/path1]                (+X, -Y)
├── [file/path2]                (+X, -Y)

➕ Added:
├── [file/path3]

➖ Removed:
├── [file/path4]
```

## 🧪 Testing Strategy

```bash
# Unit tests
pytest tests/[relevant_test].py -v

# Integration tests
pytest tests/integration/ -v

# Coverage check
make coverage

# Linting
make lint

# Full test suite
make test
```

**Test Coverage Requirements**:
- [ ] Unit tests for new functions
- [ ] Integration tests for new features
- [ ] Edge case tests
- [ ] Error handling tests
- [ ] Maintain >80% coverage

## 🔗 Related Issues

- Blocks: #[issue_number]
- Blocked by: #[issue_number]
- Related to: #[issue_number]
- Supersedes: #[issue_number]

## 💡 Additional Context

[Any additional information, screenshots, logs, or context that would help someone understand or implement this issue]

### Environment Details
- **Service**: petrosa-binance-data-extractor
- **Branch**: [branch-name]
- **K8s Namespace**: petrosa-apps
- **Dependencies**: [list any dependent services or external APIs]

### References
- [Link to docs]
- [Link to related PRs]
- [Link to Slack discussions]

## 🏷️ Labels

[List of labels to apply]

Examples:
- `bug`, `feature`, `technical-debt`, `testing`, `documentation`
- `priority:high`, `priority:critical`
- `size:S`, `size:M`, `size:L`
- `binance-data-extractor`
- `good-first-issue`, `help-wanted`

## 📅 Timeline

- **Estimated Effort**: [human-readable time estimate]
- **Target Completion**: [date or sprint]
- **Dependencies Wait Time**: [if blocked]

## ✅ Definition of Done

- [ ] Code changes implemented and reviewed
- [ ] All tests pass (unit, integration, e2e)
- [ ] Code linting passes
- [ ] Documentation updated (README, inline comments, API docs)
- [ ] Changes deployed to staging
- [ ] Changes validated in staging
- [ ] Changes deployed to production
- [ ] Monitoring/alerts configured (if applicable)
- [ ] Follow-up issues created (if needed)
- [ ] Issue closed with summary comment

---

**Created**: [YYYY-MM-DD]
**Last Updated**: [YYYY-MM-DD]
**Assignee**: @[username]
**Reviewer**: @[username]
