# executes the `help` menu by default
default:
    @just help

# lists the available `just` commands
help:
    @just --list

# uploads the wallpapers to the projectivity launcher through adb
projectivity:
    ./scripts/projectivity.sh ./wallpapers

# fetches workshop item(s) by id and adds them to workshop.json (interactive; e.g. `just fetch rhedgeco 3219522309`)
fetch username +ids:
    python3 scripts/abitoads.py fetch {{ username }} {{ ids }}

# re-hashes locally-downloaded videos and checks them against workshop.json
verify:
    python3 scripts/abitoads.py verify

# uploads any missing wallpapers to the GitHub release (e.g. `just publish` or `just publish --download`)
publish *args:
    python3 scripts/abitoads.py publish {{ args }}

# one-time: registers this server as the self-hosted runner for publish-wallpapers (prompts for a runner token and Steam username)
init-runner:
    ./scripts/init-runner.sh
