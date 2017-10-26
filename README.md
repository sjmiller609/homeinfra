# Automated Ubuntu 16.04

## what does this do?

- makes a installation usb for an unattended installation of ubuntu
- there is a feature to add files to the system after installation
- there is some ansible code to configure a system the way i like

### in a python script "create_unattended_iso.py"...

- download ubuntu 16.04 image
- mount the iso
- copy all data from iso into a temporary directory
- using the template directory ./add_to_iso, render jinja2 templates and copy into the install media (the custom iso we are making)
- jinja2 variables are queried during script run time, using the getpass module if they contain "secret" or "password"
- in this directory, there is another directory called "add_to_os" ... 

### in add_to_iso/ks.cfg.j2 ...

- in the kickstart file (ks.cfg.j2) at the bottom, you can see that the data in add_to_os is copied to the system after installation. [read about kickstart files](https://access.redhat.com/documentation/en-US/Red_Hat_Enterprise_Linux/6/html/Installation_Guide/s1-kickstart2-postinstallconfig.html), and [read about ubuntu specifics](https://help.ubuntu.com/community/KickstartCompatibility)

### in add_to_iso/add_to_os ...

- this is all the stuff we want to end up on our system.
- in /opt/ansible, there is an ansible project to set up my system.
- you should modify this code to work for your stuff. my setup should work for you, less the graphics drivers and screen size specifications located in ansible/roles/nvidia
- simply delete the line "-nvidia" from ansible/graphicsmachine.yml, and you should be good to go
- there is also a bootstrap script
- we execute this script as root after we have installed the OS

## how do i use it?

- read links above
- read the python script until you trust me
- set usb=True or usb=False
- use the script
- answer the questions
- copy data to installation media
- boot from installation media on target system
- wait a moment
- log in
- decide what to do next. execute /bootstrap.sh ?

## known issues

- writes plaintext passwords to disk
- jinja2 templates in your ansible code will not work as is because the script will try to render them at run time. this has not been an issue for me yet because i didn't use them yet, but after i do i will just change the extension that gets rendered in the python script.
- the role morning_mix does not work right now

## Disclaimer

- not my fault if you hurt yourself. MIT license
- deletes all your data by default


