import requests
import os
import sys
import re
import subprocess
from jinja2 import Environment, meta, Template
import shutil
from getpass import getpass
from random import randint
from distutils import spawn

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


# use like:
# with MountedIso(iso_path) as mount_path:
#     ...
class MountedIso():
    def __init__(self, isopath):
        self.isopath = isopath
        self.mountpath = "/tmp/isomount" + str(randint(0, 100000000))

    def __enter__(self):
        print("creating directory " + self.mountpath)
        os.mkdir(self.mountpath)
        print("mounting " + self.isopath + " to " + self.mountpath)
        command = ["sudo", "mount", "-o", "loop", self.isopath, self.mountpath]
        execute(command)
        return self.mountpath

    def __exit__(self, type, value, traceback):
        print("unmounting" + self.mountpath)
        command = ["sudo", "umount", self.mountpath]
        execute(command)
        shutil.rmtree(self.mountpath)
        print("deleting directory " + self.mountpath)


class CustomIso():
    def __init__(self, iso_path):
        if not spawn.find_executable("srm"):
            print("please install 'srm'")
            print("example: ")
            print("sudo apt-get install -y secure-delete")
            exit(1)
        self.iso_path = iso_path
        self.modified_count = 0
        self.modified_files = set()
        self.j2_vars = {}
        self._working_dir = "/tmp/workingdir" + str(randint(0, 100000000))

    def __enter__(self):
        print("creating directory " + self._working_dir)
        os.mkdir(self._working_dir)
        # we mount the iso in order to copy files from it into our new iso directory "working dir"
        with MountedIso(self.iso_path) as mount_path:
            print("copying files from " + mount_path + " to " +
                  self._working_dir)
            command = ["cp", "-rT", mount_path, self._working_dir]
            execute(command)
        return self

    def __exit__(self, type, value, traceback):
        print("recursively deleting directory " + self._working_dir)
        command = ["sudo", "rm", "-rf", self._working_dir]
        execute(command)

    def replace_in_file(self, regex_pattern, replace_with, path):

        path = os.path.join(self._working_dir, path)

        print("reading data from " + path)
        with open(path, "r") as f:
            filedata = f.read()
        regex = re.compile(regex_pattern)
        print("substituting " + regex_pattern + " with " + replace_with)
        filedata = regex.sub(replace_with, filedata)
        temp_file = "/tmp/" + str(randint(0, 1000000000))
        try:
            print("writing to temporary file " + temp_file)
            with open(temp_file, "w") as f:
                f.write(filedata)
            self._add_file(temp_file, path)
        except Exception as e:
            raise e
        finally:
            print("deleting temporary file " + temp_file)
            os.remove(temp_file)

    def write_iso(self, path="/tmp/customiso.iso", usb=True):
        print("generating new iso...")
        self.path = path
        command = [
            "sudo", "mkisofs", "-D", "-r", "-V", "UNATTENDED_UBUNTU",
            "-cache-inodes", "-J", "-l", "-b", "isolinux/isolinux.bin", "-c",
            "isolinux/boot.cat", "-no-emul-boot", "-boot-load-size", "4",
            "-boot-info-table", "-o", path, self._working_dir
        ]
        execute(command)
        if usb:
            command = ["sudo", "isohybrid", path]
            print("creating isohybrid...")
            execute(command)
        print("complete. custom iso generated after modifying " +
              str(self.modified_count) + " files.")
        return path

    def add_from_template_dir(self, path, append_working_dir=""):
        assert os.path.isdir(path), "expected " + path + " to be a directory"
        files = os.listdir(path)
        for f in files:
            file_path = os.path.join(path, f)
            if os.path.isfile(file_path):
                if file_path[-3:] == ".j2":
                    dest = os.path.join(append_working_dir, f[:-3])
                    self._add_file(file_path, dest)
                else:
                    dest = os.path.join(append_working_dir, f)
                self._add_file(file_path, dest)
            elif os.path.isdir(file_path):
                self.add_from_template_dir(
                    file_path,
                    append_working_dir=os.path.join(append_working_dir, f))
            else:
                print("ignoring " + file_path)

    def _input(self, var):
        print("============\n")
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

    def _add_file(self, src, dest):

        root = self._working_dir
        dest = os.path.join(root, dest)
        print("copying file " + src + " to " + dest)


        if src[-3:] == ".j2":
            print("reading data from jinjia template")
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
            print("rendering jinjia template")
            data = template.render(**self.j2_vars)
            temp_file = src.replace(".j2", "")
            try:
                print("creating temporary file "+temp_file)
                with open(temp_file, "w") as f:
                    f.write(data)
                command = ["sudo", "cp", temp_file, dest]
                execute(command)
            except Exception as e:
                raise e
            finally:
                # use srm in case we wrote a secret to disk
                print("deleting "+temp_file+" with srm")
                command = ["srm",temp_file]
                execute(command)
                #os.remove(temp_file)
        else:
            command = ["sudo", "cp", src, dest]
            execute(command)

        if not dest in self.modified_files:
            self.modified_count += 1
        self.modified_files.add(dest)



def main():

    url = "http://releases.ubuntu.com/16.04.3/ubuntu-16.04.3-server-amd64.iso"
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = "ubuntu-16.04.3-server-amd64.iso"
    template_dir = "add_to_iso"
    #where we will download the iso to
    if not os.path.isdir(os.path.join(dir_path,"downloads")):
        os.mkdir(os.path.join(dir_path,"downloads"))
    iso_path = os.path.join(dir_path, "downloads", filename)
    #where our files to add to the custom iso are located
    files_path = os.path.join(dir_path, template_dir)

    #download file
    download_file(url, iso_path)
    '''
    adding these files:
    isolinux/txt.cfg
    ubuntu-auto.seed
    ks.cfg"
    '''
    with CustomIso(iso_path) as custom:
        custom.j2_vars["install_mount"] = "/dev/cdrom"
        custom.add_from_template_dir(files_path)
        custom.replace_in_file("timeout\s+[0-9]+", "timeout 3",
                               "isolinux/isolinux.cfg")
        iso_path = custom.write_iso(
            path=os.path.join(dir_path, "customubuntu.iso"), usb=True)

    print("custom iso created.\n")
    print("to write to USB drive:")
    print("sudo dd if=" + iso_path + " of=/dev/<usb device> bs=4M && sync")


if __name__ == "__main__":
    main()
