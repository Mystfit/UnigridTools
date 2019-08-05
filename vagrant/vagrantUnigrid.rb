def vagrant_unigrid config
  config.vm.define :unigridtools do |unigridtools_config|
  unigridtools_config.vm.hostname = :unigridtools
  unigridtools_config.vm.provision "shell", inline: <<-SHELL
    pushd /vagrant
    sudo /usr/local/bin/singularity build UnigridTools.sif UnigridTools.def
    popd
  SHELL
end
