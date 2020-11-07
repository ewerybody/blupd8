RELEASES_URL = 'https://download.blender.org/release/'

import os
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

LINK_PATTERN = '<a href="'
LINK_END = '</a>'
LEN_LINK = len(LINK_PATTERN)
LETTERS = ''.join(chr(i) for i in range(97, 123))
PROJECT = 'Blender'


class Blupd8(QtCore.QObject):
    def __init__(self):
        super(Blupd8, self).__init__()
        self._releases = None
        self._progress_callback = None
        self.manager = QtNetwork.QNetworkAccessManager(self)

    def get_releases(self, progress_callback=None):
        if progress_callback is None:
            self._progress_callback = self._backup_report
        else:
            self._progress_callback = progress_callback

        if self._releases is None:
            request = QtNetwork.QNetworkRequest(QtCore.QUrl(RELEASES_URL))
            request.setRawHeader(b'User-Agent', b'MyOwnBrowser 1.0')

            log.info('Looking up "%s" ...' % RELEASES_URL)
            reply = self.manager.get(request)
            reply.finished.connect(self._on_releases_finish)
            reply.downloadProgress.connect(self._on_progress)
            reply.error[QtNetwork.QNetworkReply.NetworkError].connect(self._on_error)
            reply.sslErrors.connect(self._on_error)
            reply.readyRead.connect(self._on_ready_read)

            log.info('Fetching releases ...')
        else:
            self._releases

    def _on_error(self, x):
        x
        pass

    def _on_releases_finish(self):
        reply = self.sender()
        data = reply.readAll().data().decode()

        self._releases = {}
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
            name_version = line[link_end + 2:name_end].rstrip('/')
            name, version = _split_version(name_version)
            nfo = self._releases.setdefault(name, {})
            nfo[version] = link

        log.info(
            'Fetched %i projects, %i versions.\nLatest "%s" versions: %s',
            len(self._releases),
            sum(len(vs) for vs in self._releases.values()),
            PROJECT,
            ', '.join(sorted(self._releases[PROJECT].keys(), reverse=True)[:5])
        )

    def _on_progress(self, x):
        x
        reply = self.sender()
        self._progress_callback

    def _backup_report(self):
        reply = self.sender()

    def _on_ready_read(self):
        reply = self.sender()


def test():
    updater = Blupd8()
    updater.get_releases()
    updater
    # while not updater._releases:
    #     time.sleep(0.1)
    # print(updater._releases)


def main():
    app = QtWidgets.QApplication.instance()
    if app is None:
        # app = QtWidgets.QApplication([])
        app = QtCore.QCoreApplication([])
        # test()
        updater = Blupd8()
        updater.get_releases()
        app.exec_()
    else:
        test()


def _split_version(name_version):
    _name_version = name_version.lower()
    for i, c in enumerate(_name_version):
        if c in LETTERS:
            continue
        return name_version[:i], name_version[i:].lstrip('.')
    return name_version, ''


if __name__ == "__main__":
    main()
