{
  # resolve this repo's lfs files when Nix fetches the source
  inputs.self.lfs = true;

  outputs = { self }: {
    wallpapers = self + "/wallpapers";
  };
}
