import os
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
        latest


def have_versions():
    have = []
    for item in os.scandir(HOME):
        if item.is_dir() and item.name.startswith(blupd8.PROJECT):
            have.append(item.name)
    return have


if __name__ == '__main__':
    main()
