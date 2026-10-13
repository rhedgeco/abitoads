# Non-flake entry point. Returns the path to the wallpapers directory.
#
# Flake users should prefer the `wallpapers` output in flake.nix.
# This file is here for `import ./. ` style consumers.
{
  src ? ./.,
}:
src + "/wallpapers"
