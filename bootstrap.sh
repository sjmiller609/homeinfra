
sudo apt-add-repository ppa:ansible/ansible
sudo apt-get update
sudo apt-get install -y \
	software-properties-common \
	git \
        ansible
sudo ansible --version
git clone https://github.com/sjmiller609/homeinfra.git
cd homeinfra
ansible-playbook -i ./hosts.yaml deploy.yml
