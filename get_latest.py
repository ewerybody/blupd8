import os
import subprocess

import blupd8

HOME = r'C:\Users\eric\io\tools\blender'


def main():
    releases = blupd8.get_releases()
    have = have_versions()

    releases[blupd8.PROJECT]
    latest = sorted(releases[blupd8.PROJECT])[-1]
    version_name = blupd8.PROJECT + '-' + latest

    if version_name not in have:
        blupd8.download(latest, HOME, 'windows', 'zip')
    else:
        executable_path = os.path.join(have[version_name], blupd8.PROJECT + '.exe')
        if not os.path.isfile(executable_path):
            raise FileNotFoundError('No blender.exe here! %s' % executable_path)

        pid = subprocess.Popen([executable_path])
        print('started blender! pid: %s (%s)' % (pid, executable_path))


def have_versions():
    have = {}
    for item in os.scandir(HOME):
        if item.is_dir() and item.name.startswith(blupd8.PROJECT):
            have[item.name] = item.path
    return have


if __name__ == '__main__':
    main()
