import os
import sys
import time
import logging
import zipfile
from tqdm import tqdm
from PySide2 import QtNetwork, QtWidgets, QtCore

if __name__ == '__main__':
    NAME = os.path.splitext(os.path.basename(__file__))[0]
    logging.basicConfig()
else:
    NAME = __name__
log = logging.getLogger(NAME)
log.setLevel(10)


RELEASES_URL = 'https://download.blender.org/release/'
BUILDER_URL = 'https://builder.blender.org/download/daily/'
BUILDER_ALL = BUILDER_URL + 'archive/'
LINK_PATTERN = '<a href="'
LINK_END = '</a>'
LEN_LINK = len(LINK_PATTERN)
LETTERS = ''.join(chr(i) for i in range(97, 123))
PROJECT = 'blender'


class Blupd8(QtCore.QObject):
    def __init__(self):
        super(Blupd8, self).__init__()
        self._releases = None
        self._progress_callback = None
        self.manager = QtNetwork.QNetworkAccessManager(self)
        self._finished = False
        self._data = None
        self._progress = None

    def read_page(self, url):
        reply = self._prepare_request(url, _nop)
        reply.finished.connect(self._page_finished)
        self.wait_for_finish()
        return self._data

    def _page_finished(self):
        reply = self.sender()
        self._data = reply.readAll().data().decode()

    def get_releases(self, progress_callback=None):
        if self._releases is None:
            log.info('Looking up "%s" ...' % RELEASES_URL)
            self._releases = _parse_releases(self.read_page(RELEASES_URL))
            # reply = self._prepare_request(RELEASES_URL, progress_callback)
            # reply.finished.connect(self._on_releases_finish)

        log.info(
            'Fetched %i projects, %i versions.\nLatest "%s" versions: %s',
            len(self._releases),
            sum(len(vs) for vs in self._releases.values()),
            PROJECT,
            ', '.join(sorted(self._releases[PROJECT].keys(), reverse=True)[:5]),
        )

        return self._releases

    def download(self, version, target_dir, platform, pack_type, progress_callback=None):
        version_name = f'{PROJECT}-{version}'
        target_path = os.path.join(target_dir, version_name)
        if os.path.isdir(target_path):
            raise FileExistsError('The target directory alredy exists!')

        release_page_url = f'{RELEASES_URL}{PROJECT.title()}{version}/'
        page_data = self.read_page(release_page_url)
        packages = _parse_download_page(page_data, release_page_url)
        for pack_name, pack_nfo in packages.items():
            if platform in pack_name and pack_name.endswith(pack_type.lower()):
                break
        else:
            raise RuntimeError(
                f'No package found for "{version}" type:{platform}/{pack_type}!\n'
                'Available are:\n  %s' % '\n  '.join(packages)
            )

        tmp_file = os.path.join(os.getenv('TEMP'), f'_{PROJECT}_tmp_dl_{version}.zip')
        if not os.path.isfile(tmp_file):
            self._file = QtCore.QSaveFile(tmp_file)
            if self._file.open(QtCore.QIODevice.WriteOnly):
                log.info('Looking up "%s" ...' % pack_nfo['url'])
                reply = self._prepare_request(pack_nfo['url'], progress_callback)
                reply.finished.connect(self._on_download_finished)
                reply.readyRead.connect(self._on_download_ready)
            else:
                error = self._file.errorString()
                log.error(f'Cannot open device: {error}')

            self.wait_for_finish()
            if os.path.isfile(tmp_file):
                log.info('Downloaded: %s', tmp_file)
            else:
                raise RuntimeError('Download failed!')

        self._unzip(tmp_file, target_path)

    def _unzip(self, tmp_file, target_path):
        import shutil



        try:
            with zipfile.ZipFile(tmp_file) as tmp_zip:
                # look for a subfolder within the zip
                remove_sub = False
                if all('/' in z.filename for z in tmp_zip.filelist):
                    root = tmp_zip.filelist[0].filename.split('/', 1)[0]
                    # make sure the subdir is the same everywhere
                    if all(z.filename.startswith(f'{root}/') for z in tmp_zip.filelist):
                        remove_sub = True
                num_files = len(tmp_zip.filelist)
                for i, zitem in enumerate(tmp_zip.filelist):
                    self._on_progress(i, num_files)
                    if zitem.is_dir():
                        continue

                    if remove_sub:
                        path = zitem.filename.split('/', 1)[1]
                    else:
                        path = zitem.filename

                    tgt_path = os.path.abspath(os.path.join(target_path, path))
                    tgt_dir = os.path.dirname(tgt_path)
                    if tgt_dir and not os.path.isdir(tgt_dir):
                        os.makedirs(tgt_dir)

                    with tmp_zip.open(zitem) as source, open(tgt_path, "wb") as target:
                        shutil.copyfileobj(source, target)

        except zipfile.BadZipFile as error:
            raise RuntimeError('Error Unpacking Update! (%s)' % tmp_file)


    def _on_download_ready(self):
        reply = self.sender()
        if reply.error() == QtNetwork.QNetworkReply.NoError:
            self._file.write(reply.readAll())

    def _on_download_finished(self):
        self._file.commit()

    def _prepare_request(self, url, progress_callback=None):
        self._progress_callback = progress_callback

        request = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        request.setRawHeader(b'User-Agent', b'MyOwnBrowser 1.0')

        reply = self.manager.get(request)
        reply.finished.connect(self._on_finish)
        reply.downloadProgress.connect(self._on_progress)
        reply.error[QtNetwork.QNetworkReply.NetworkError].connect(self._on_error)
        reply.sslErrors.connect(self._on_error)
        return reply

    def _on_error(self, x):
        log.error(x)

    def _on_progress(self, current, total):
        if self._progress_callback is None:
            self._progress_callback = self._backup_report
        self._progress_callback(current, total)

    def _backup_report(self, current, total):
        if self._progress is None and total != -1:
            self._progress = tqdm(total=total, unit='bytes')

        if self._progress is not None:
            self._progress.update(current)

    def wait_for_finish(self):
        while not self._finished:
            QtWidgets.QApplication.instance().processEvents()
            time.sleep(0.01)
        self._finished = False
        self._progress = None
        self._progress_callback = None

    def _on_finish(self):
        self._finished = True


class StandaloneContext:
    def __init__(self):
        self.app = None
        self.app_started = False

    def __enter__(self):
        app = QtWidgets.QApplication.instance()
        if app is None:
            self.app = QtCore.QCoreApplication([])
            self.app_started = True

    def __exit__(self, *args):
        if self.app_started:
            self.app.quit()


def get_releases():
    with StandaloneContext():
        updater = Blupd8()
        releases = updater.get_releases()
    return releases


def download(version, target_dir, platform, pack_type, callback=None):
    with StandaloneContext():
        updater = Blupd8()
        updater.download(version, target_dir, platform, pack_type, callback)


def test():
    updater = Blupd8()
    updater.get_releases()
    updater


def _parse_releases(data):
    releases = {}
    for line in data.split('\r\n'):
        line = line.strip()
        if not line.startswith(LINK_PATTERN):
            continue
        link_end = line.find('">')
        if link_end == -1:
            continue
        link = line[LEN_LINK:link_end]
        if not link.endswith('/'):
            # This is a file! We're looking for subfolders ...
            continue

        name_end = line.find(LINK_END, link_end)
        name_version = line[link_end + 2 : name_end].rstrip('/').lower()
        name, version = _split_version(name_version)
        nfo = releases.setdefault(name, {})
        nfo[version] = link
    return releases


def _parse_download_page(data, url):
    packages = {}
    for line in data.split('\r\n'):
        line = line.strip()
        if not line.startswith(LINK_PATTERN):
            continue
        link_end = line.find('">')
        if link_end == -1:
            continue
        link = line[LEN_LINK:link_end]
        name_end = line.find(LINK_END, link_end)
        name = line[link_end + 2 : name_end]
        date, time_, size = line[name_end + 4 :].split()
        packages[name] = {
            'url': f'{url}{link}',
            'date': date,
            'time': time_,
            'size': int(size),
        }

    return packages


def _nop(*args):
    pass


def _split_version(name_version):
    _name_version = name_version.lower()
    for i, c in enumerate(_name_version):
        if c in LETTERS:
            continue
        return name_version[:i], name_version[i:].lstrip('.')
    return name_version, ''


if __name__ == '__main__':
    test()
