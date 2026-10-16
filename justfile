# executes the `help` menu by default
default:
    @just help

# lists the available `just` commands
help:
    @just --list

# pushes wallpapers to the projectivity launcher through adb
projectivity path=".wallpapers":
    ./scripts/projectivity.sh {{ path }}

# registers workshop item(s) by id into workshop.json
register +ids:
    python3 scripts/abitoads.py register {{ ids }}

# downloads every manifest item from Steam and collects them into .wallpapers
fetch *args:
    python3 scripts/abitoads.py fetch {{ args }}

# re-hashes the collected .wallpapers/ videos and checks them against workshop.json
verify:
    python3 scripts/abitoads.py verify

# installs, registers, and primes the steam login to launch a self-hosted runner
runner:
    ./scripts/runner.sh
