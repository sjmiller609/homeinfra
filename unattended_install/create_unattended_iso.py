import requests
import os
import sys
import subprocess
import shutil
from getpass import getpass

#import time


def execute(command):
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # Poll process for new output until finished
    while True:
        nextline = process.stdout.readline()
        if nextline == '' and process.poll() is not None:
            break
        sys.stdout.write(nextline)
        sys.stdout.flush()

    output = process.communicate()[0]
    exitCode = process.returncode

    if not exitCode:
        return output
    else:
        raise Exception(command, exitCode, output)


def download_file(url, path):
    if os.path.isfile(path):
        print("already downloaded iso. continuing.")
        return path
    filename = os.path.basename(path)
    print("downloading to " + filename)
    # NOTE the stream=True parameter
    r = requests.get(url, stream=True)
    chunk_size = 4 * 1024 * 1024  # 1 MB
    #mb_per_sec = 0
    #alpha = 0.2
    #last_chunk = time.time()
    with open(path + ".part", 'wb') as f:
        i = 0
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:  # filter out keep-alive new chunks
                #now = time.time()
                #mb_per_sec = \
                #(1/alpha) * mb_per_sec + alpha * float(size(chunk)/(1024*1024))/(now-last_chunk)
                #last_chunk = now
                f.write(chunk)
                i += 1
                sys.stdout.write("\r" + str(i * float(chunk_size) /
                                            (1024 * 1024)) +
                                 " MB  ")  #@ "+str(mb_per_sec)+" MB/s   ")
                sys.stdout.flush()
    os.rename(path + ".part", path)
    print("\ndownload complete.")
    return path


class MountedIso():
    def __init__(self, isopath):
        self.isopath = isopath
        self.mountpath = "/tmp/isomount"
        os.mkdir(self.mountpath)

    def __enter__(self):
        command = ["sudo", "mount", "-o", "loop", self.isopath, self.mountpath]
        execute(command)
        return self.mountpath

    def __exit__(self, type, value, traceback):
        command = ["sudo", "umount", self.mountpath]
        execute(command)

    def __del__(self):
        shutil.rmtree(self.mountpath)


class CustomIso():
    def __init__(self, mountediso):
        self.working_dir = "/tmp/workingdir"
        os.mkdir(self.working_dir)
        self.generated_iso = False
        self.modified_count = 0
        self.modified_files = set()
        with mountediso as mount_path:
            command = ["cp", "-rT", mount_path, self.working_dir]
            execute(command)

    def add_file(self, src, dest):
        if not dest in self.modified_files:
            self.modified_count += 1
        self.modified_files.add(dest)
        command = ["sudo","cp",src,dest]
        execute(command)

    def get_iso(self, path="/tmp/customiso.iso", usb=True):
        print("generating new iso...")
        self.path = path
        command = [
            "sudo", "mkisofs", "-D", "-r", "-V", "UNATTENDED_UBUNTU",
            "-cache-inodes", "-J", "-l", "-b", "isolinux/isolinux.bin", "-c",
            "isolinux/boot.cat", "-no-emul-boot", "-boot-load-size", "4",
            "-boot-info-table", "-o", path, self.working_dir
        ]
        execute(command)
        command = ["isohybrid", path]
        self.generated_iso = True
        print("complete. custom iso generated after modifying " +
              str(self.modified_count) + " files.")
        return path

    def __del__(self):
        command = ["sudo", "rm", "-rf", self.working_dir]
        execute(command)


def main():
    username = raw_input("username: ")
    full_name = raw_input("full name: ")
    password = getpass("password (no visual feedback): ")
    url = "http://releases.ubuntu.com/16.04.3/ubuntu-16.04.3-desktop-amd64.iso"
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = "ubuntu-16.04.3-desktop-amd64.iso"
    path = os.path.join(dir_path, filename)
    download_file(url, path)
    mounted_iso = MountedIso(path)
    new_iso = CustomIso(mounted_iso)
    working_dir = new_iso.working_dir
    new_iso.add_file(
        os.path.join(dir_path, "txt.cfg"),
        os.path.join(working_dir, "isolinux", "txt.cfg"))
    with open("ks.cfg.j2", "r") as f:
        ks_data = f.read()
    print(ks_data)
    ks_data = ks_data.replace("{{ password }}",password)
    ks_data = ks_data.replace("{{ username }}",username)
    ks_data = ks_data.replace("{{ full_name }}",full_name)
    print(ks_data)
   #TODO 
    new_iso.add_file(
        os.path.join(dir_path, "ks.cfg.j2"),
        os.path.join(working_dir, "isolinux", "txt.cfg"))
    #new_iso.add_file(
    new_iso_path = new_iso.get_iso(path=os.path.join(dir_path,"customubuntu.iso"))
    print(new_iso_path)


if __name__ == "__main__":
    main()
