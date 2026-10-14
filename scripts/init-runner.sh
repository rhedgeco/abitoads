#!/usr/bin/env bash
# Bootstraps a GitHub Actions self-hosted runner on this server so it can run
# the publish-wallpapers workflow (download from Steam -> upload to the release).
#
# This is meant to be run ONCE on the maintainer's own server, from the repo
# root (the justfile ensures that). It:
#   1. downloads and configures the runner with the `steam-publish` label,
#   2. writes STEAM_USER and GH_TOKEN to the runner's .env so every job inherits
#      them in its environment,
#   3. installs and starts the runner as a service.
#
# Steam and gh credentials stay on this server. The workflow runs everything
# through `devenv shell`, so the runner itself only needs devenv (which provides
# gh, steamcmd, just, python3 and secretspec); nothing else has to be installed.
# The publish step sets SECRETSPEC_PROVIDER=env so the tool's secretspec SDK
# resolves the two env vars in-process (it errors if either is unset).
# Before the
# first publish run, prime the Steam session once with:
#   steamcmd +login "$STEAM_USER" +quit
# (approve the Steam Guard prompt; the cached sentry makes CI logins silent).

set -euo pipefail

REPO="rhedgeco/abitoads"
RUNNER_LABEL="steam-publish"
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner-abitoads}"
RUNNER_VERSION="${RUNNER_VERSION:-2.321.0}"

die() {
    printf 'error: %s\n' "$1" >&2
    exit 1
}

command -v curl >/dev/null || die "curl is required but not found on PATH."
command -v tar >/dev/null || die "tar is required but not found on PATH."

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

# The runner reads this .env in its install dir and injects the variables into
# every job's environment, where the publish step (with SECRETSPEC_PROVIDER=env)
# resolves them via the secretspec env provider.
printf 'Recording secrets in the runner .env\n'
{
    printf 'STEAM_USER=%s\n' "$steam_user"
    printf 'GH_TOKEN=%s\n' "$github_token"
} >.env

printf 'Installing and starting the runner service\n'
sudo ./svc.sh install
sudo ./svc.sh start

printf '\nRunner is registered with label %s.\n' "$RUNNER_LABEL"
printf 'Next: prime the Steam session once so CI logins are silent:\n'
printf '  steamcmd +login %s +quit\n' "$steam_user"
