#!/usr/bin/env bash
# Bootstraps a GitHub Actions self-hosted runner on this server so it can run
# the publish-wallpapers workflow (download from Steam -> upload to the release).
#
# This is meant to be run ONCE on the maintainer's own server, from the repo
# root (the justfile ensures that). It:
#   1. downloads and configures the runner with the `steam-publish` label,
#   2. stores STEAM_USER and GH_TOKEN in secretspec so publish can inject them,
#   3. installs and starts the runner as a service.
#
# Steam and gh credentials stay on this server. The workflow runs everything
# through `devenv shell`, so the runner itself only needs devenv (which provides
# gh, steamcmd, just, python3 and secretspec); nothing else has to be installed.
# The secrets are declared in secretspec.toml and injected into publish by
# `secretspec run`, so no secret values are written to the repo or exported into
# the job's environment ahead of time. Before the first publish run, prime the
# Steam session once with:  steamcmd +login "$STEAM_USER" +quit  (approve the
# Steam Guard prompt; the cached sentry makes CI logins silent).

set -euo pipefail

REPO="rhedgeco/abitoads"
RUNNER_LABEL="steam-publish"
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner-abitoads}"
RUNNER_VERSION="${RUNNER_VERSION:-2.321.0}"
# secretspec stores the values here, outside any repo checkout, matching the
# `server` provider declared in secretspec.toml. Keeping it under ~/.config
# means it is stable across the runner's per-job checkouts and never in a repo.
SECRET_ENV="${SECRET_ENV:-$HOME/.config/abitoads/.env}"
SECRET_PROVIDER="dotenv:${SECRET_ENV}"

die() {
    printf 'error: %s\n' "$1" >&2
    exit 1
}

command -v curl >/dev/null || die "curl is required but not found on PATH."
command -v tar >/dev/null || die "tar is required but not found on PATH."
command -v secretspec >/dev/null \
    || die "secretspec not found on PATH; run this inside the devenv shell."

repo_root="$PWD"
[ -f "$repo_root/secretspec.toml" ] \
    || die "secretspec.toml not found; run this from the repo root."

# A registration token is short-lived; the maintainer gets one from:
#   GitHub -> repo Settings -> Actions -> Runners -> New self-hosted runner
registration_token="${RUNNER_TOKEN:-}"
if [ -z "$registration_token" ]; then
    printf 'Runner registration token (from repo Settings -> Actions -> Runners): '
    read -r registration_token
fi
[ -n "$registration_token" ] || die "a runner registration token is required."

steam_user="${STEAM_USER:-}"
if [ -z "$steam_user" ]; then
    printf 'Steam username that owns Wallpaper Engine: '
    read -r steam_user
fi
[ -n "$steam_user" ] || die "a Steam username is required."

# A GitHub token for gh. devenv provides the gh binary but not its credentials,
# so publish needs a token with permission to edit releases on this repo.
github_token="${GH_TOKEN:-}"
if [ -z "$github_token" ]; then
    printf 'GitHub token for gh (needs repo contents write; from https://github.com/settings/tokens): '
    read -r github_token
fi
[ -n "$github_token" ] || die "a GitHub token is required for gh to edit releases."

printf 'Storing secrets with secretspec at %s\n' "$SECRET_ENV"
mkdir -p "$(dirname "$SECRET_ENV")"
printf '%s' "$steam_user" | secretspec set STEAM_USER --provider "$SECRET_PROVIDER"
printf '%s' "$github_token" | secretspec set GH_TOKEN --provider "$SECRET_PROVIDER"

printf 'Setting up runner in %s\n' "$RUNNER_DIR"
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

if [ ! -x "./config.sh" ]; then
    case "$(uname -m)" in
        x86_64) arch="x64" ;;
        aarch64 | arm64) arch="arm64" ;;
        *) die "unsupported CPU architecture: $(uname -m)" ;;
    esac
    tarball="actions-runner-linux-${arch}-${RUNNER_VERSION}.tar.gz"
    url="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${tarball}"
    printf 'Downloading runner %s (%s)\n' "$RUNNER_VERSION" "$arch"
    curl -fsSL -o "$tarball" "$url"
    tar xzf "$tarball"
    rm -f "$tarball"
fi

./config.sh \
    --unattended \
    --url "https://github.com/${REPO}" \
    --token "$registration_token" \
    --name "$(hostname)-abitoads" \
    --labels "$RUNNER_LABEL" \
    --replace

printf 'Installing and starting the runner service\n'
sudo ./svc.sh install
sudo ./svc.sh start

printf '\nRunner is registered with label %s.\n' "$RUNNER_LABEL"
printf 'Next: prime the Steam session once so CI logins are silent:\n'
printf '  steamcmd +login %s +quit\n' "$steam_user"
