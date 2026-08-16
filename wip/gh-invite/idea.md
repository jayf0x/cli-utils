# `gh invite` — concept (deferred)

Full extension concept, parked for later. Not built yet — see `gh-bulk-collab-simple.sh`
for the current minimal version.

## Command shape

```
gh invite -u <user> -r <repo1 repo2 ... | all> [--max N] [--dry-run] [--permission push|pull|admin|maintain|triage]
gh invite --accept all -u <user>
gh invite --revoke all -u <user>
```

## `-u` (target user)

- Check whether `<user>` matches an account already authenticated locally via `gh auth switch --user`.
- Local-login presence is NOT sufficient proof of correct identity — it only tells you
  a session exists, not that it's the *intended* account.
- Before granting access, resolve `<user>` via `gh api /users/<user>` and surface
  identifying info (name, bio, avatar, account age) for the operator to visually confirm.
- Require explicit confirmation (`y/N` or typed username) before any grant, regardless
  of local-login status. Treat unfamiliar/unconfirmed accounts as higher-friction, not
  local-login-status as the gate.

## `-r` (repos)

- Accepts an explicit space-separated list of repo names, or the literal `all`.
- `all` triggers a live fetch of the invoking (owner) account's repos.
- **Decision needed:** does `all` mean owner-owned repos only, or also repos visible
  via org membership? Default should be **owner-owned only**; org repos opt-in via
  a separate flag (e.g. `--include-orgs`), since org repos carry different blast radius
  and often different permission models already.
- `--max N` caps how many repos are touched in one run (default suggested: 100).
- Should skip archived repos by default (mirrors the current simple-script behavior);
  consider `--include-archived` if ever needed.

## `--dry-run`

- Lists exactly what would be invited/revoked without making any API calls.
- Should be treated as close to mandatory for first-time use — a bulk grant/revoke tool
  with no preview is easy to misfire once and regret.

## `--accept`

- Separate mode: switches local `gh` auth context to `<user>` (`gh auth switch --user <user>`),
  lists pending repository invitations, accepts all of them.
- Requires `<user>` to already be authenticated locally (`gh auth login` done beforehand);
  this tool does not create new sessions.
- Open question: should accept happen automatically as a follow-up step to invite (chained),
  or always remain a manual second command? Leaning manual — keeps the two account contexts
  (owner vs invitee) clearly separated and auditable.

## `--revoke`

- `all` here should NOT mean "all repos owned by me" — it should mean "all repos where
  `<user>` currently has collaborator access," fetched fresh at revoke time.
- Rationale: invites can fail, be manually granted outside this tool, or already be revoked
  elsewhere — owner's repo list and invitee's actual access list can drift apart.
- Should enumerate current collaborator status per-repo before acting (same spirit as
  dry-run for invite).

## Permission level

- Currently hardcoded to `push` in the simple script.
- Full version: expose as `--permission` flag (`pull`, `push`, `admin`, `maintain`, `triage`),
  default `push`, with the same confirm-before-grant friction for `admin`.

## Packaging

- Ship as a `gh` extension (`gh extension install <owner>/gh-invite`) so it becomes a real
  subcommand rather than a standalone script — matches how `-u`/`-r` flag style is expected
  to feel native to the `gh` CLI.

## Rate limits

- Not a practical concern: authenticated REST calls get 5000/hour; even hundreds of repos
  is a small fraction of that budget.
