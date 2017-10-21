import requests
import os
import sys
import re
import subprocess
from jinja2 import Environment, meta, Template
import shutil
from getpass import getpass
from random import randint

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
        try:
            shutil.rmtree(self.mountpath)
        except Exception: pass
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
        try:
            self.clean()
        except Exception: pass
        os.mkdir(self.working_dir)
        self.generated_iso = False
        self.modified_count = 0
        self.modified_files = set()
        self.j2_vars = {}
        with mountediso as mount_path:
            command = ["cp", "-rT", mount_path, self.working_dir]
            execute(command)

    def clean(self):
        command = ["sudo", "rm", "-rf", self.working_dir]
        execute(command)

    def _input(self, var):
        value = ""
        if "secret" in var or "password" in var:
            value1 = "0"
            first = True
            while value != value1:
                if not first:
                    print("do not match.")
                first = False
                value = getpass("input " + var + " (no visual feedback): ")
                value1 = getpass("input " + var + " again: ")
        else:
            if sys.version_info >= (3, 0):
                value = input("input " + var + ": ")
            else:
                value = raw_input("input " + var + ": ")
        return value

    def add_file(self, src, dest):

        root = self.working_dir
        dest = os.path.join(root, dest)

        if not dest in self.modified_files:
            self.modified_count += 1
        self.modified_files.add(dest)

        if src[-3:] == ".j2":
            with open(src, "r") as f:
                j2_data = f.read()
            env = Environment()
            parser = env.parse(j2_data)
            undeclared = meta.find_undeclared_variables(parser)
            for var in undeclared:
                if var not in self.j2_vars:
                    value = self._input(var)
                    self.j2_vars[var] = value
            template = Template(j2_data)
            data = template.render(**self.j2_vars)
            temp_file = src.replace(".j2", "")
            try:
                with open(temp_file, "w") as f:
                    f.write(data)
                command = ["sudo", "cp", temp_file, dest]
                execute(command)
            except Exception as e:
                raise e
            finally:
                os.remove(temp_file)
        else:
            command = ["sudo", "cp", src, dest]
            execute(command)

    def replace_in_file(self, regex_pattern, replace_with, path):

        path = os.path.join(self.working_dir,path)

        with open(path, "r") as f:
            filedata = f.read()
        regex = re.compile(regex_pattern)
        filedata = regex.sub(replace_with, filedata)
        temp_file = "/tmp/" + str(randint(0, 1000000000))
        try:
            with open(temp_file, "w") as f:
                f.write(filedata)
            self.add_file(temp_file, path)
        except Exception as e:
            raise e
        finally:
            os.remove(temp_file)

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
        command = ["sudo", "isohybrid", path]
        print("creating isohybrid...")
        execute(command)
        self.generated_iso = True
        print("complete. custom iso generated after modifying " +
              str(self.modified_count) + " files.")
        return path

    def __del__(self):
        self.clean()


def main():
    #url = "http://releases.ubuntu.com/16.04.3/ubuntu-16.04.3-desktop-amd64.iso"
    url = "http://releases.ubuntu.com/16.04.3/ubuntu-16.04.3-server-amd64.iso"
    dir_path = os.path.dirname(os.path.realpath(__file__))
    #filename = "ubuntu-16.04.3-desktop-amd64.iso"
    filename = "ubuntu-16.04.3-server-amd64.iso"
    path = os.path.join(dir_path, filename)
    download_file(url, path)
    mounted_iso = MountedIso(path)
    new_iso = CustomIso(mounted_iso)
    new_iso.j2_vars["install_mount"] = "/dev/cdrom"

    print("adding files")
    new_iso.add_file(os.path.join(dir_path, "txt.cfg"), "isolinux/txt.cfg")
    new_iso.add_file(
        os.path.join(dir_path, "ubuntu-auto.seed"), "ubuntu-auto.seed")
    new_iso.add_file(os.path.join(dir_path, "ks.cfg.j2"), "ks.cfg")

    #sed -i -r 's/timeout\s+[0-9]+/timeout 3/g' ubuntu_files/isolinux/isolinux.cfg
    new_iso.replace_in_file("timeout\s+[0-9]+", "timeout 3", "isolinux/isolinux.cfg")

    #new_iso.add_file(
    new_iso_path = new_iso.get_iso(path=os.path.join(dir_path,
                                                     "customubuntu.iso"))
    print(new_iso_path)


if __name__ == "__main__":
    main()
