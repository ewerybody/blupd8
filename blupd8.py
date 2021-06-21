import os
import sys
import time
import logging
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

    def read_page(self, url):
        reply = self._prepare_request(url)
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

    def download(self, version, target_dir, progress_callback=None):
        release_page_url = f'{RELEASES_URL}{PROJECT.title()}{version}/'
        page_data  = self.read_page(release_page_url)
        page_data

        tmp_file = os.path.join(os.getenv('TEMP'), f'_{PROJECT}_tmp_dl_{version}.zip')
        self._file = QtCore.QSaveFile(tmp_file)

        if self.file.open(QtCore.QIODevice.WriteOnly):
            reply = self._prepare_request(url, progress_callback)
            reply.finished.connect(self._on_download_finished)
            reply.readyRead.connect(self._on_download_ready)
        else:
            error = self.file.errorString()
            print(f'Cannot open device: {error}')

        log.info('Looking up "%s" ...' % url)
        reply = self._prepare_request(url, progress_callback)
        reply.finished.connect(self._on_download_finished)
        log.info('Fetching release %s ...', version)
        self.wait_for_finish()

        log.info('downloaded: %s', tmp_file)
        tmp_file

    def _on_download_ready(self):
        reply = self.sender()
        if reply.error() == QtNetwork.QNetworkReply.NoError:
                self._file.write(reply.readAll())

    def _on_download_finished(self):
        self._file.commit()

    def _prepare_request(self, url, progress_callback=None):
        if progress_callback is None:
            self._progress_callback = self._backup_report
        else:
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

    def _on_progress(self, received, total):
        if self._progress_callback is not None:
            self._progress_callback(received, total)

    def _backup_report(self, received, total):
        log.info('Fetched %i bytes or %i ...', received, total)

    def _on_ready_read(self):
        reply = self.sender()

    def wait_for_finish(self):
        while not self._finished:
            QtWidgets.QApplication.instance().processEvents()
            time.sleep(0.01)
        self._finished = False

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


def download(version, target_dir, callback=None):
    with StandaloneContext():
        updater = Blupd8()
        updater.download(version, target_dir, callback)


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


def _split_version(name_version):
    _name_version = name_version.lower()
    for i, c in enumerate(_name_version):
        if c in LETTERS:
            continue
        return name_version[:i], name_version[i:].lstrip('.')
    return name_version, ''


if __name__ == '__main__':
    test()
