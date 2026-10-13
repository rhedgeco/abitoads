# executes the `help` menu by default
default:
    @just help

# lists the available `just` commands
help:
    @just --list

# uploads the wallpapers to the projectivity launcher through adb
projectivity:
    ./scripts/projectivity.sh ./wallpapers
