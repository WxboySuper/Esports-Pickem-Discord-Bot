# GitHub Issue and Pull Request Labeling System

This document outlines the labeling system used in the Esports Pick'em Discord Bot repository to organize both issues and pull requests.

## Overview

Our labeling system is designed to provide quick visual cues about:
- Which project phase an item belongs to
- The priority level of the work
- The type of work required
- The current status of the issue or pull request
- Which component of the system is affected
- The estimated effort required

## Label Categories

### Phase Labels (Timeline-based)

These labels indicate which project phase an issue belongs to, helping to organize work according to our development timeline.

| Label | Color | Description |
|-------|-------|-------------|
| `phase:foundation` | `#C5DEF5` (Light Blue) | Foundation phase tasks (Week 1-2) |
| `phase:data` | `#BFD4F2` (Pale Blue) | Data Management phase tasks (Week 2-3) |
| `phase:core` | `#D4C5F5` (Light Purple) | Core Features phase tasks (Week 3-4) |
| `phase:automation` | `#C2E0C6` (Light Green) | Automation phase tasks (Week 4-5) |
| `phase:optimization` | `#FBCA04` (Yellow) | Optimization phase tasks (Week 5-6) |
| `phase:enhancement` | `#FEF2C0` (Light Yellow) | Enhancement phase tasks (Week 6-7) |
| `phase:polish` | `#F9D0C4` (Light Salmon) | Polish phase tasks (Week 7-8) |
| `phase:deployment` | `#D4C5F5` (Light Purple) | Testing & Deployment tasks |
| `phase:post-launch` | `#C5DEF5` (Light Blue) | Post-Launch tasks |

### Priority Labels

These labels indicate the urgency with which an issue should be addressed.

| Label | Color | Description |
|-------|-------|-------------|
| `priority:critical` | `#E11D21` (Bright Red) | Must be addressed immediately |
| `priority:high` | `#EB6420` (Orange) | High priority to be addressed soon |
| `priority:medium` | `#FBCA04` (Yellow) | Normal priority |
| `priority:low` | `#009800` (Green) | Low urgency, can be addressed later |

### Type Labels

These labels categorize what kind of work the issue involves.

| Label | Color | Description |
|-------|-------|-------------|
| `type:feature` | `#0E8A16` (Green) | New feature implementation |
| `type:bug` | `#D93F0B` (Red Orange) | Bug fixes |
| `type:enhancement` | `#0052CC` (Blue) | Improvements to existing features |
| `type:documentation` | `#0075CA` (Blue) | Documentation updates |
| `type:refactor` | `#FBCA04` (Yellow) | Code refactoring |
| `type:test` | `#D4C5F5` (Light Purple) | Testing related |
| `type:devops` | `#5319E7` (Purple) | CI/CD and deployment tasks |

### Status Labels

These labels indicate the current state of an issue or pull request in the development workflow.

| Label | Color | Description |
|-------|-------|-------------|
| `status:blocked` | `#B60205` (Dark Red) | Blocked by another issue/dependency |
| `status:in-progress` | `#0E8A16` (Green) | Currently in development |
| `status:review` | `#FBCA04` (Yellow) | Ready for review |
| `status:discussion` | `#D4C5F5` (Light Purple) | Needs further discussion |
| `status:duplicate` | `#CCCCCC` (Gray) | Duplicate issue |

### Pull Request-Specific Labels

These labels are specifically for pull requests to indicate their review status.

| Label | Color | Description |
|-------|-------|-------------|
| `pr:needs-review` | `#FBCA04` (Yellow) | PR needs initial review |
| `pr:changes-requested` | `#E11D21` (Bright Red) | Changes requested during review |
| `pr:approved` | `#0E8A16` (Green) | PR approved and ready to merge |
| `pr:merge-conflict` | `#B60205` (Dark Red) | PR has merge conflicts that need resolution |
| `pr:wip` | `#D4C5F5` (Light Purple) | Work in progress, not ready for full review |

### Component Labels

These labels indicate which part of the system an issue pertains to.

| Label | Color | Description |
|-------|-------|-------------|
| `component:database` | `#1D76DB` (Blue) | Database related |
| `component:api` | `#5319E7` (Purple) | API integration |
| `component:bot-framework` | `#0E8A16` (Green) | Core bot framework |
| `component:commands` | `#FBCA04` (Yellow) | Bot commands |
| `component:match-tracking` | `#0075CA` (Blue) | Match tracking functionality |
| `component:picks` | `#D93F0B` (Red Orange) | Pick system |
| `component:leaderboard` | `#EB6420` (Orange) | Leaderboard functionality |
| `component:notifications` | `#BFD4F2` (Pale Blue) | Notifications system |
| `component:admin` | `#5319E7` (Purple) | Administrative features |
| `component:monitoring` | `#C2E0C6` (Light Green) | Logging and monitoring |

### Effort Labels

These labels provide an estimate of the amount of work required to complete the issue.

| Label | Color | Description |
|-------|-------|-------------|
| `effort:trivial` | `#C2E0C6` (Light Green) | Quick fix |
| `effort:small` | `#FBCA04` (Yellow) | Less than a day of work |
| `effort:medium` | `#EB6420` (Orange) | 1-3 days of work |
| `effort:large` | `#D93F0B` (Red Orange) | More than 3 days of work |

## Label Usage Guidelines

### Best Practices

1. **Multiple Labels**: Apply one label from each relevant category to each issue or PR
2. **Required Labels**: 
   - Issues: At minimum, each issue should have a phase, priority, and type label
   - PRs: At minimum, each PR should have a phase, component, and PR-specific status label
3. **Update Labels**: Update labels as the status of items changes
4. **Search by Label**: Use label filters to create focused work views

### Example Label Combinations

#### For Issues
- New feature in initial development:
  - `phase:foundation` + `priority:high` + `type:feature` + `status:in-progress` + `component:database` + `effort:medium`

- Critical bug during deployment:
  - `phase:deployment` + `priority:critical` + `type:bug` + `component:bot-framework` + `effort:small`

#### For Pull Requests
- Feature implementation PR ready for review:
  - `phase:core` + `type:feature` + `component:pick-system` + `pr:needs-review` + `effort:medium`

- Bug fix PR with requested changes:
  - `phase:deployment` + `type:bug` + `component:bot-framework` + `pr:changes-requested` + `effort:small`

- Work-in-progress PR for notification system:
  - `phase:enhancement` + `type:feature` + `component:notifications` + `pr:wip` + `effort:large`

## Maintenance

Review and update this labeling system periodically to ensure it continues to meet project needs. Consider adding new labels or retiring unused ones as the project evolves.

## Using Labels in Workflows

### For Issues
- Use labels to prioritize work during sprint planning
- Filter issues by phase to track project progress
- Sort by priority to identify what to work on next

### For Pull Requests
- Use PR labels to identify which PRs need attention
- Filter PRs by component to find related changes
- Identify PRs that are ready to merge vs. those that need more work

### Automation Opportunities
Consider setting up GitHub Actions to:
- Automatically add `pr:needs-review` when a PR is opened
- Move PRs to `pr:changes-requested` when changes are requested
- Add `pr:approved` when a PR receives approval