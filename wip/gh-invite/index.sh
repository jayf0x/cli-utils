#!/usr/bin/env bash
# gh-bulk-collab-simple.sh
#
# Minimal single-use tool:
#   1. Invite <username> as collaborator to every non-archived repo owned by the
#      currently authenticated gh account.
#   2. Switch gh auth to <username> and accept every pending repository invitation.
#
# Requirements:
#   - gh CLI, already logged in to BOTH accounts (gh auth login, done twice)
#   - jq
#
# Usage:
#   ./gh-bulk-collab-simple.sh <invitee-username>

set -euo pipefail

PERMISSION="push"

[[ $# -ne 1 ]] && { echo "Usage: $0 <invitee-username>"; exit 1; }
INVITEE="$1"

echo "==> Fetching non-archived repos owned by the current gh account..."
REPOS=$(gh repo list --json nameWithOwner,isArchived,isFork -L 1000 \
          --jq '.[] | select(.isArchived == false and .isFork == false) | .nameWithOwner')

if [[ -z "$REPOS" ]]; then
  echo "No matching repos found. Nothing to do."
  exit 0
fi

echo "Repos to invite '$INVITEE' to:"
echo "$REPOS" | sed 's/^/  - /'
echo
read -rp "Proceed with inviting '$INVITEE' as collaborator (permission: $PERMISSION) to the above repos? [y/N] " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

echo "==> Sending invitations..."
echo "$REPOS" | while read -r repo; do
  echo -n "  $repo... "
  if gh api -X PUT "/repos/${repo}/collaborators/${INVITEE}" \
       -f permission="$PERMISSION" >/dev/null 2>&1; then
    echo "invited"
  else
    echo "skipped (already collaborator or failed)"
  fi
done

echo
echo "==> Switching gh auth to invitee account: $INVITEE"
gh auth switch --user "$INVITEE"

echo "==> Fetching pending invitations for $INVITEE..."
IDS=$(gh api /user/repository_invitations --jq '.[].id')

if [[ -z "$IDS" ]]; then
  echo "No pending invitations found (they may already be accepted, or not yet propagated)."
  exit 0
fi

echo "==> Accepting invitations..."
echo "$IDS" | while read -r id; do
  echo -n "  invitation $id... "
  if gh api -X PATCH "/user/repository_invitations/${id}" >/dev/null 2>&1; then
    echo "accepted"
  else
    echo "failed"
  fi
done

echo
echo "Done."
