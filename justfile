# executes the `help` menu by default
default:
    @just help

# lists the available `just` commands
help:
    @just --list

# pushes wallpapers to the projectivity launcher through adb (defaults to the collected .wallpapers dir; pass a path to override)
projectivity path=".wallpapers":
    ./scripts/projectivity.sh {{ path }}

# registers workshop item(s) by id into workshop.json (interactive; e.g. `just register 3219522309`)
register +ids:
    python3 scripts/abitoads.py register {{ ids }}

# downloads every manifest item from Steam and collects them into .wallpapers/ (pass --update to refresh manifest hashes instead of failing on a mismatch)
fetch *args:
    python3 scripts/abitoads.py fetch {{ args }}

# re-hashes the collected .wallpapers/ videos and checks them against workshop.json
verify:
    python3 scripts/abitoads.py verify

# cuts a new release snapshot (v1, v2, ...) with the full current set, becoming releases/latest (e.g. `just publish` or `just publish --download`)
publish *args:
    python3 scripts/abitoads.py publish {{ args }}

# installs, registers (first run only), primes Steam login and runs this server's self-hosted runner for publish-wallpapers (idempotent; ctrl-c to stop)
runner:
    ./scripts/runner.sh
