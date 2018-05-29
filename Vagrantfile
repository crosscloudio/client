# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.ssh.forward_agent = true

  # crosscloud:client:core
  config.vm.define "core" do |core|
    core.vm.hostname = "crosscloud-client-core"
    core.vm.box = "ubuntu/xenial64"
    
    # Disable automatic box update checking. If you disable this, then
    # boxes will only be checked for updates when the user runs
    # `vagrant box outdated`. This is not recommended.
    core.vm.box_check_update = false
    
    # Create a forwarded port mapping which allows access to a specific port
    # within the machine from a port on the host machine. In the example below,
    # accessing "localhost:8080" will access port 80 on the guest machine.
    # core.vm.network "forwarded_port", guest: 80, host: 8080
    
    # Create a private network, which allows host-only access to the machine
    # using a specific IP.
    core.vm.network "private_network", ip: "10.0.0.100"
    
    # Share an additional folder to the guest VM. The first argument is
    # the path on the host to the actual folder. The second argument is
    # the path on the guest to mount the folder. And the optional third
    # argument is a set of non-required options.
    
    core.vm.synced_folder ".", "/crosscloud"
    
    core.vm.provider "virtualbox" do |vb|
      vb.name = "crosscloud-client-core"
      vb.gui = false
      vb.memory = "1024"
      vb.cpus = 2
    end
    
    core.vm.provision :shell, path: "bootstrap-core-client.sh"
    
    # Enable provisioning with a shell script. Additional provisioners such as
    # Puppet, Chef, Ansible, Salt, and Docker are also available. Please see the
    # documentation for more information about their specific syntax and use.
    # config.vm.provision "shell", inline: <<-SHELL
    #   apt-get update
    #   apt-get install -y apache2
    # SHELL
  end
end
