# Repository Agents (Agent README)

This file is the single source-of-truth README for automated agents, integrations, and tools that interact with this repository. It exists to help human maintainers and automated agents operate safely and consistently.

See https://agents.md for general guidance on agent design and policies.

Important: store all credentials and tokens in GitHub Secrets or a secure vault — never commit secrets to the repository.

---

## Purpose & Audience
- For maintainers: explain what agents do, who owns them, how to onboard/offboard them, and where config lives.
- For agents (automations, bots): a machine-readable and human-readable guide describing expectations and required behavior when operating on this repo.

This file resides in the repository root as `AGENTS.md`.

---

## High-level rules for all agents
1. Least privilege: request only the permissions required for the task. Prefer GitHub Apps or workflow-level permissions.
2. Secrets: read tokens only from configured secrets (not from repository files).
3. Transparency: every automated change must open a pull request with a clear description and link to an onboarding issue when applicable.
4. Approval confirmation: agents MUST NOT push changes or open PRs without an explicit human confirmation recorded for that operation. The canonical confirmation phrase for this repo is:

   "@Copilot Accepted Confirmation: Are you sure?"

   - An authorized human must post this exact line in the relevant conversation thread, issue, or PR comment to grant permission for a specific operation initiated by an agent.
   - Agents must include the human confirmation comment permalink in the PR body when creating the PR and must reference the person who posted it.
5. Size & scope: when opening a PR, include a size label or reference to `.github/SIZE_GUIDELINES.md` and follow `CONTRIBUTING.md`.
6. Audit: log actions and include a short note in the PR describing what was changed and why.

---

## Onboarding an agent (checklist for humans)
1. Open an issue titled `onboard: <agent-name>` describing:
   - The agent's owner
   - The exact operations it will perform
   - Required permissions with rationale
   - Config location and secrets needed
2. Add or update the agent entry in `AGENTS.md` (this file) and open a PR that references the onboarding issue.
3. After the PR is merged, install or create the integration and add secrets to repo/org secrets.
4. Perform a verified smoke run (if applicable) and document the first successful run in the onboarding issue.
5. Periodically (quarterly) review the agent and its granted permissions.

Agent entry template (when adding an entry):
- Name:
- Integration type: (GitHub App, OAuth App, GitHub Actions, Service account, CLI tool)
- Identity: (GitHub username, app id, service account)
- Purpose: (what the agent does)
- Config location: (path to workflow or external service)
- Permissions required: (exact scopes needed)
- Owner / contact: (team or username)
- Secret storage: (which secret key in repo/org secrets)
- Onboarded (date / issue / PR):
- Confirmation policy: (how the agent should request/receive human confirmation)
- Notes / rollback plan:

---

## Required behavior for agent-authored PRs
- PR title should start with the agent name in square brackets, e.g. `[Copilot] Fix README typo`.
- PR body MUST include:
  - A brief summary of the change
  - The onboarding issue reference (if applicable)
  - The exact human confirmation comment permalink that authorized the action and the author of that comment
  - Size (XS/S/M/L/XL) per `.github/SIZE_GUIDELINES.md`
  - A short test or verification checklist
- Add labels as appropriate (`docs`, `automation`, `dependency`) and request review from the owner listed in the agent entry.
- If multiple files are changed, prefer splitting into smaller PRs to match the project's size guidelines.

---

## Examples

### GitHub Copilot (chat-driven suggestions / this assistant)
- Name: GitHub Copilot / @copilot
- Integration type: Chat / GitHub App
- Identity: @copilot (or the installed GitHub App)
- Purpose: Draft issues, propose files, and open PRs when explicitly authorized.
- Config location: n/a (chat-driven)
- Permissions required: push/write to create branches and PRs (GRANT ONLY WHEN NEEDED)
- Owner / contact: repository maintainers (WxboySuper)
- Secret storage: not applicable for chat; use GitHub App installation for push access
- Onboarded: record onboarding issue/PR link
- Confirmation policy: requires the exact human confirmation phrase in the conversation or an issue/PR comment before opening a PR. The agent must embed the confirmation comment permalink in the PR body.
- Notes / rollback plan: remove app installation or revoke collaborator access; rotate tokens.

### Jules / Alternative CLI or service agent
- Name: Jules (or <tool-name>)
- Integration type: CLI / Service account
- Identity: service account user or bot user
- Purpose: e.g., automation for dependency updates, scaffolding, CI ops
- Config location: `.github/workflows/<workflow>.yml` or external service URL
- Permissions required: minimal required scopes (e.g., contents: read/write)
- Owner / contact: (person/team)
- Secret storage: store token as `JULES_TOKEN` in repo/org secrets
- Onboarded: record onboarding issue/PR link
- Confirmation policy: same confirmation phrase; require human comment and include permalink in the PR body
- Notes / rollback plan: revoke token, disable workflow, and open an incident issue

---

## Security & operations
- Rotate tokens periodically and immediately if compromise is suspected.
- Limit access to only the necessary repositories and scopes.
- Prefer GitHub Apps (finer-grained permissions) over personal access tokens.
- Keep an audit of installed agents and their permissions; review quarterly.

---

## Disabling or removing an agent
1. Revoke tokens or uninstall the app immediately if the agent behaves unexpectedly.
2. Disable any associated workflows in `.github/workflows/`.
3. Open an incident issue describing mitigation and root cause analysis.
4. Mark the agent entry in `AGENTS.md` as `retired` with the date and reason and link the incident issue.

---

## Governance & contact
- Repository owner: `WxboySuper`
- Contact for automation onboarding: open an issue labeled `automation` or `infrastructure` and ping `@WxboySuper`.

---

## Contributing updates to this file
- To add or change an entry, open a PR targeting `main` and reference an onboarding or removal issue.
- Agents must follow the confirmation and PR-body requirements above when proposing changes.

---

## Related docs
- `CONTRIBUTING.md` — contributor workflow and PR conventions
- `.github/SIZE_GUIDELINES.md` — PR sizing guidance
- `LICENSE` — project license
