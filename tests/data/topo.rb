def get_mac(oui="28:b7:ad")
  "Generate a MAC address"
  nic = (1..3).map{"%0.2x"%rand(256)}.join(":")
  return "#{oui}:#{nic}"
end

NUM_SPINES = 2
NUM_LEAVES = 2
NUM_EXIT_LEAVES = 0
NUM_SERVERS_PER_LEAF = 2

BASE_PORT = 10900
DUMMY_PORT = 10800
SERVER_BASE_PORT = BASE_PORT + NUM_SPINES*100

SPINE_NOS = "junos"
LEAF_NOS = "junos"
EXIT_NOS = "junos"

NOS_MEM = {
  "cumulus" => 768,
  "nxos" => 6144,
  "junos" => 2048,
  "eos" => 2048
}

NOS_BOX = {
  "cumulus" => "CumulusCommunity/cumulus-vx",
  "nxos" => "cisco/nxosv",
  "junos" => "juniper/vqfx10k-re",
  "eos" => "arista/veos"
}


SERVER_BOX = "generic/ubuntu1804"

Vagrant.require_version ">= 2.1.0"
Vagrant.configure("2") do |config|

  config.vm.provider :libvirt do |domain|
    domain.management_network_name = "default"
    domain.management_network_address = "192.168.123.0/24"
  end
  
  pfe_port_id = 1
  spinelist = []
  # spines
  (1..NUM_SPINES).each do |id|
    re_name = ( "spine" + "%02d"%id).to_sym
    spinelist << re_name

    config.vm.define re_name do |node|
      node.vm.hostname = re_name.to_s
      node.vm.synced_folder ".", "/vagrant", id: "vagrant-root", disabled: true
      node.vm.box = NOS_BOX[SPINE_NOS]
      
      node.vm.provider :libvirt do |v|
        v.memory = NOS_MEM[SPINE_NOS]
        v.management_network_mac = "44:38:39:01:01:"+"%02d"%id

        if SPINE_NOS == "junos"
          v.nic_model_type = "e1000"
        end
      end

      if SPINE_NOS != "cumulus"
        node.vm.guest = :tinycore
      end

      if SPINE_NOS == "junos"
        node.vm.network :private_network,
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.1",
                        :libvirt__tunnel_local_port => BASE_PORT + pfe_port_id,
                        :libvirt__tunnel_ip => "127.0.0.1",
                        :libvirt__tunnel_port => BASE_PORT + pfe_port_id + 1,
                        :libvirt__iface_name => "spine" + "%02d"%id + "pfe",
                        auto_config: false

        node.vm.network :private_network,
                        # reserved port
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.1",
                        :libvirt__tunnel_local_port => DUMMY_PORT+id,
                        :libvirt__tunnel_ip => "127.0.0.4",
                        :libvirt__tunnel_port => DUMMY_PORT,
                        :libvirt__iface_name => "spine%02d-resv"%id,
                        auto_config: false
      end

      # Regular leaves first
      (1..NUM_LEAVES).each do |lid|
        node.vm.network :private_network,
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.1",
                        :libvirt__tunnel_local_port => BASE_PORT + id*100 + lid,
                        :libvirt__tunnel_ip => "127.0.0.2",
                        :libvirt__tunnel_port => BASE_PORT + id*100 + lid,
                        :libvirt__iface_name => ("leaf"+"%02d"%lid),
                        auto_config: false
      end

      # Exit leaves next
      exit_base_port = BASE_PORT + id*100 + NUM_LEAVES
      (1..NUM_EXIT_LEAVES).each do |lid|
        node.vm.network :private_network,
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.1",
                        :libvirt__tunnel_local_port => exit_base_port + lid,
                        :libvirt__tunnel_ip => "127.0.0.2",
                        :libvirt__tunnel_port => exit_base_port + lid,
                        :libvirt__iface_name => ("exit"+"%02d"%lid),
                        auto_config: false
      end
    end

    if SPINE_NOS == "junos"
      pfe_name = ( "spine" + "%02d"%id + "-pfe").to_sym

      config.vm.define pfe_name do |node|
        node.vm.box = "juniper/vqfx10k-pfe"
        node.vm.guest = :tinycore
        node.vm.synced_folder ".", "/vagrant", id: "vagrant-root", disabled: true
        node.ssh.insert_key = false
        node.ssh.shell = "/bin/ash"
        node.ssh.username = "tc"

        node.vm.provider :libvirt do |v|
          v.nic_model_type = "e1000"
        end
        
        node.vm.network :private_network,
                        # leaf01-pfe-internal-1 <--> leaf01-internal-1
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.1",
                        :libvirt__tunnel_local_port => BASE_PORT + pfe_port_id + 1,
                        :libvirt__tunnel_ip => "127.0.0.1",
                        :libvirt__tunnel_port => BASE_PORT + pfe_port_id,
                        :libvirt__iface_name => "spine-pfe" + "%02d"%id,
                        auto_config: false
        pfe_port_id += 2
      end
    end
  end

  #  Leaves
  pfe_port_id = 1
  leaflist = []
  (1..NUM_LEAVES).each do |id|
    re_name = ( "leaf" + "%02d"%id).to_sym
    leaflist << re_name

    config.vm.define re_name do |node|
      node.vm.hostname = re_name.to_s
      node.vm.synced_folder ".", "/vagrant", id: "vagrant-root", disabled: true
      node.vm.box = NOS_BOX[LEAF_NOS]
      
      node.vm.provider :libvirt do |v|
        v.memory = NOS_MEM[LEAF_NOS]
        v.management_network_mac = "44:38:39:01:02:"+"%02d"%id

        if LEAF_NOS == "junos"
          v.nic_model_type = "e1000"
        end
      end

      if LEAF_NOS != "cumulus"
        node.vm.guest = :tinycore
      end

      if LEAF_NOS == "junos"
        node.vm.network :private_network,
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.2",
                        :libvirt__tunnel_local_port => BASE_PORT + pfe_port_id,
                        :libvirt__tunnel_ip => "127.0.0.2",
                        :libvirt__tunnel_port => BASE_PORT + pfe_port_id + 1,
                        :libvirt__iface_name => ("leaf%02d-pfe"%id),
                        auto_config: false

        node.vm.network :private_network,
                        # reserved port
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.2",
                        :libvirt__tunnel_local_port => DUMMY_PORT+id,
                        :libvirt__tunnel_ip => "127.0.0.4",
                        :libvirt__tunnel_port => DUMMY_PORT,
                        :libvirt__iface_name => "leaf%02d-resv"%id,
                        auto_config: false
      end

      # Uplink ports first
      (1..NUM_SPINES).each do |lid|
        node.vm.network :private_network,
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.2",
                        :libvirt__tunnel_local_port => BASE_PORT + lid*100 + id,
                        :libvirt__tunnel_ip => "127.0.0.1",
                        :libvirt__tunnel_port => BASE_PORT + lid*100 + id,
                        :libvirt__iface_name => ("spine" + "%02d"%lid),
                        auto_config: false
      end

      # server ports next
      (1..NUM_SERVERS_PER_LEAF).each do |lid|
        node.vm.network :private_network,
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.2",
                        :libvirt__tunnel_local_port => SERVER_BASE_PORT + id*100 + lid,
                        :libvirt__tunnel_ip => "127.0.0.3",
                        :libvirt__tunnel_port => SERVER_BASE_PORT + id*100 + lid,
                        :libvirt__iface_name => ("server" + id.to_s + lid.to_s),
                        auto_config: false
      end
    end

    if LEAF_NOS == "junos"
      pfe_name = ( "leaf" + "%02d"%id + "-pfe").to_sym

      config.vm.define pfe_name do |node|
        node.vm.box = "juniper/vqfx10k-pfe"
        node.vm.guest = :tinycore
        node.vm.synced_folder ".", "/vagrant", id: "vagrant-root", disabled: true
        node.ssh.insert_key = false
        node.ssh.shell = "/bin/ash"
        node.ssh.username = "tc"
        
        node.vm.provider :libvirt do |v|
          v.nic_model_type = "e1000"
        end
        
        node.vm.network :private_network,
                        # leaf01-pfe-internal-1 <--> leaf01-internal-1
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.2",
                        :libvirt__tunnel_local_port => BASE_PORT + pfe_port_id + 1,
                        :libvirt__tunnel_ip => "127.0.0.2",
                        :libvirt__tunnel_port => BASE_PORT + pfe_port_id,
                        :libvirt__iface_name => ("leaf%02d-pfe"%id),
                        auto_config: false
        pfe_port_id += 2
      end
    end
  end

  # Exit Leaves
  # Don't reset the pfe_port_id, as exit leaves also use 127.0.0.2 IP
  exitlist = []
  (1..NUM_EXIT_LEAVES).each do |id|
    re_name = ( "exit" + "%02d"%id).to_sym
    exitlist << re_name

    config.vm.define re_name do |node|
      node.vm.hostname = re_name.to_s
      node.vm.synced_folder ".", "/vagrant", id: "vagrant-root", disabled: true
      node.vm.box = NOS_BOX[EXIT_NOS]
      
      node.vm.provider :libvirt do |v|
        v.memory = NOS_MEM[EXIT_NOS]
        v.management_network_mac = "44:38:39:01:03:"+"%02d"%id

        if EXIT_NOS == "junos"
          v.nic_model_type = "e1000"
        end
      end

      if EXIT_NOS != "cumulus"
        node.vm.guest = :tinycore
      end

      if EXIT_NOS == "junos"
        node.vm.network :private_network,
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.2",
                        :libvirt__tunnel_local_port => BASE_PORT + pfe_port_id,
                        :libvirt__tunnel_ip => "127.0.0.2",
                        :libvirt__tunnel_port => BASE_PORT + pfe_port_id + 1,
                        :libvirt__iface_name => "exit" + "%02d"%id + "-pfe",
                        auto_config: false

        node.vm.network :private_network,
                        # reserved port
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.3",
                        :libvirt__tunnel_local_port => DUMMY_PORT+id,
                        :libvirt__tunnel_ip => "127.0.0.4",
                        :libvirt__tunnel_port => DUMMY_PORT,
                        :libvirt__iface_name => "exit%02d-resv"%id,
                        auto_config: false
      end

      (1..NUM_SPINES).each do |lid|
        exit_base_port = BASE_PORT + lid*100 + NUM_LEAVES
        node.vm.network :private_network,
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.2",
                        :libvirt__tunnel_local_port => exit_base_port + id,
                        :libvirt__tunnel_ip => "127.0.0.1",
                        :libvirt__tunnel_port => exit_base_port + id,
                        :libvirt__iface_name => ("spine" + "%02d"%lid),
                        auto_config: false
      end
    end

    if EXIT_NOS == "junos"
      pfe_name = ( "exit" + "%02d"%id + "-pfe").to_sym

      config.vm.define pfe_name do |node|
        node.vm.box = "juniper/vqfx10k-pfe"
        node.vm.guest = :tinycore
        node.vm.synced_folder ".", "/vagrant", id: "vagrant-root", disabled: true
        node.ssh.insert_key = false
        node.ssh.shell = "/bin/ash"
        node.ssh.username = "tc"
        
        node.vm.provider :libvirt do |v|
          v.nic_model_type = "e1000"
        end
        
        node.vm.network :private_network,
                        # leaf01-pfe-internal-1 <--> leaf01-internal-1
                        :mac => "#{get_mac()}",
                        :libvirt__tunnel_type => "udp",
                        :libvirt__tunnel_local_ip => "127.0.0.2",
                        :libvirt__tunnel_local_port => BASE_PORT + pfe_port_id + 1,
                        :libvirt__tunnel_ip => "127.0.0.2",
                        :libvirt__tunnel_port => BASE_PORT + pfe_port_id,
                        :libvirt__iface_name => "exit-pfe" + "%02d"%id,
                        auto_config: false
        pfe_port_id += 2
      end
    end
  end

  # Servers
  serverlist = []
  (1..NUM_LEAVES).each do |lid|
    (1..NUM_SERVERS_PER_LEAF).each do |id|
      s_name = ( "server" + lid.to_s + "%02d"%id ).to_sym
      serverlist << s_name

      config.vm.define s_name do |server|
        server.vm.hostname = s_name.to_s
        server.vm.box = SERVER_BOX
        server.vm.synced_folder ".", "/vagrant", id: "vagrant-root", disabled: true
        
        server.vm.network :private_network,
                          :mac => "#{get_mac()}",
                          :libvirt__tunnel_type => "udp",
                          :libvirt__tunnel_local_ip => "127.0.0.3",
                          :libvirt__tunnel_local_port => SERVER_BASE_PORT + lid*100 + id,
                          :libvirt__tunnel_ip => "127.0.0.2",
                          :libvirt__tunnel_port => SERVER_BASE_PORT + lid*100 + id,
                          :libvirt__iface_name => ("leaf" + "%02d"%lid),
                          auto_config: false
        
      end
    end
  end

  if SPINE_NOS != "cumulus"
    spinevars = {"ansible_network_os" => SPINE_NOS}
  else
    spinevars = {}
  end

  if LEAF_NOS != "cumulus"
    leafvars = {"ansible_network_os" => LEAF_NOS}
  else
    leafvars = {}
  end

  if EXIT_NOS != "cumulus"
    exitvars = {"ansible_network_os" => EXIT_NOS}
  else
    exitvars = {}
  end
        
  config.vm.provision "ansible" do |ansible|
    ansible.compatibility_mode = "2.0"
    ansible.playbook = "dummy.yml"
    ansible.groups = {
      "leaf" => leaflist,
      "spine" => spinelist,
      "exit" => exitlist,
      "servers" => serverlist,
      "all:children" => ["leaf", "spine", "exit", "servers"],
      "leaf:vars" => leafvars,
      "spine:vars" => spinevars,
      "exit:vars" => exitvars,
    }
  end
  

end
