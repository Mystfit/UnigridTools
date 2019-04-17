Vagrant.configure('2') do |config|
  # Base VM options
  eval File.read('bldr-core/VagrantFile.template')

  # VM specific options
  config.vm.define :unigridtools do |unigridtools_config|
      unigridtools_config.vm.hostname = :unigridtools
      unigridtools_config.vm.provision "shell", inline: <<-SHELL
        pushd /vagrant
        sudo /usr/local/bin/singularity build UnigridTools.sif UnigridTools.def
        popd
      SHELL
  end
end
