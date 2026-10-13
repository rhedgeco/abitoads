# executes the `help` menu by default
default:
    @just help

# lists the available `just` commands
help:
    @just --list

# uploads the wallpapers to the projectivity launcher through adb
projectivity:
    ./scripts/projectivity.sh ./wallpapers

# fetches workshop item(s) by id and adds them to workshop.json (interactive; e.g. `just fetch myuser 3219522309`)
fetch username +ids:
    ./scripts/fetch-wallpaper.sh {{ username }} {{ ids }}
