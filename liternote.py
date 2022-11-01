#! encoding = utf-8

""" Read papers!
One paper one day keeps the doctor away
"""

import sqlite3
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QIcon, QTextOption, QPixmap, QImage
from os.path import realpath, dirname, isfile
from os.path import join as path_join
from os import remove as os_remove
import sys

ROOT = dirname(realpath(__file__))
DB = 'liternote.db'

COLOR_BLUE = '#0066cc'
COLOR_RED = '#cc0000'

FIELDS = ('title', 'author', 'thesis', 'hypothesis', 'method', 'finding', 'comment')
GENRES = ('Astronomy', 'Code', 'Experiment', 'Instrum', 'Theory', 'Review')


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle('Literature Note')
        self.setStyleSheet('font-size: 12pt')
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.resize(QtCore.QSize(900, 600))
        self.setWindowIcon(QIcon('icon/icon_literature.png'))
        self.showMaximized()
        self.clipboard = QtWidgets.QApplication.clipboard()
        self.conn, self.cursor = create_or_open_db(path_join(ROOT, DB))
        self.dialogSearch = DialogSearch(parent=self)
        self.dialogBibKey = DialogBibKey(parent=self)
        self.dialogAddImg = DialogAddImg(self.clipboard, parent=self)
        self.dialogViewImg = DialogViewImg(parent=self)
        self.dialogDelImg = DialogDelImg(parent=self)
        self.dialogPatchKey = DialogPatchBibkey(parent=self)
        self.dialogNewEntry = DialogNewEntry(parent=self)
        self.dialogChangeBibkey = DialogChangeBibkey(parent=self)
        self.dialogDelImg.accepted.connect(self.del_img)
        self.dialogSearch.btnSearch.clicked.connect(self.search_fulltext)
        self.dialogSearch.btnLoad.clicked.connect(self.load_entry_fulltext)
        self.dialogSearch.btnSelTags.clicked.connect(self.select_search_tags)
        self.dialogBibKey.btnSearch.clicked.connect(self.search_bibkey)
        self.dialogBibKey.btnLoad.clicked.connect(self.load_entry_bibkey)
        self.dialogBibKey.prevPage.clicked.connect(self.dialog_bibkey_prev)
        self.dialogBibKey.nextPage.clicked.connect(self.dialog_bibkey_next)
        self.dialogPatchKey.btnOk.clicked.connect(self.check_patchkey)
        self.dialogPickSearchTags = DialogMultiTag(color=COLOR_BLUE, parent=self)
        self.dialogPickDelTags = DialogMultiTag(color=COLOR_RED, parent=self)

        menuBar = MenuBar(parent=self)
        toolBar = ToolBar(parent=self)
        self.setMenuBar(menuBar)
        self.addToolBar(toolBar)
        menuBar.actionNewEntry.triggered.connect(self.add_new_entry)
        menuBar.actionSaveEntry.triggered.connect(self.save_entry)
        menuBar.actionAddImg.triggered.connect(self.add_img)
        menuBar.actionViewImg.triggered.connect(self.view_img)
        menuBar.actionDeleteImg.triggered.connect(self.open_dialog_del_img)
        menuBar.actionSearchBibkey.triggered.connect(self.dialogBibKey.showNormal)
        menuBar.actionSearchDoc.triggered.connect(self.dialogSearch.showNormal)
        toolBar.actionNewEntry.triggered.connect(self.add_new_entry)
        toolBar.actionSaveEntry.triggered.connect(self.save_entry)
        toolBar.actionAddImg.triggered.connect(self.add_img)
        toolBar.actionViewImg.triggered.connect(self.view_img)
        toolBar.actionDeleteImg.triggered.connect(self.open_dialog_del_img)
        toolBar.actionSearchBibkey.triggered.connect(self.dialogBibKey.showNormal)
        toolBar.actionSearchDoc.triggered.connect(self.dialogSearch.showNormal)

        self.mw = MainWidget(parent=self)
        self.setCentralWidget(self.mw)
        self.mw.tagBox.btnDel.clicked.connect(self.tagbox_del_tag)
        self.mw.tagBox.btnAdd.clicked.connect(self.tagbox_add_tag)
        self.mw.btnChangeBibkey.clicked.connect(self.change_bibkey)

        # load the last entry
        self.mw.loadEntry(*db_select_last_entry(self.cursor))
        self.refresh_all_tags()
        # load the first page of the full bibkey list into the bibkey dialog
        self.search_bibkey()

    def closeEvent(self, ev):
        # ask if save the last operation
        if self.mw.is_edited:
            if q_save_entry(self):
                self.save_entry()
        self.conn.close()
        ev.accept()

    def refresh_all_tags(self):
        # refresh the tag list
        all_tags = db_query_all_tags(self.cursor)
        self.dialogPickSearchTags.setTags(all_tags)
        self.mw.tagBox.comboTags.clear()
        self.mw.tagBox.comboTags.addItems(all_tags)
        self.mw.tagBox.comboTags.adjustSize()

    def tagbox_add_tag(self):
        """ Add a tag to the current tagbox """
        newtag = self.mw.tagBox.comboTags.currentText()
        if newtag.strip():
            self.mw.tagBox.dispTags.addTag(newtag)

    def tagbox_del_tag(self):
        """ Remove tags in the current tagbox """
        current_tags = self.mw.tagBox.dispTags.tags()
        self.dialogPickDelTags.setTags(current_tags)
        self.dialogPickDelTags.exec()
        if self.dialogPickDelTags.result():
            tags_to_del = self.dialogPickDelTags.getSelectedTags()
            for tag in tags_to_del:
                current_tags.remove(tag)
            self.mw.tagBox.dispTags.setTags(current_tags)

    def select_search_tags(self):
        self.dialogPickSearchTags.exec()
        if self.dialogPickSearchTags.result() == QtWidgets.QDialog.Accepted:
            n = self.dialogPickSearchTags.getSelectedNum()
            if n > 0:
                self.dialogSearch.btnSelTags.setText('{:d} tags'.format(n))
            else:
                self.dialogSearch.btnSelTags.setText('all tags')

    def change_bibkey(self):
        self.dialogChangeBibkey.oldBibkey.setText(self.mw.inpBibKey.text())
        self.dialogChangeBibkey.exec()
        if self.dialogChangeBibkey.result() == QtWidgets.QDialog.Accepted:
            old_key = self.mw.inpBibKey.text()
            new_key = self.dialogChangeBibkey.editNewBibkey.text()
            try:
                db_replace_bibkey(self.conn, self.cursor, old_key, new_key)
                self.mw.inpBibKey.setText(new_key)
            except sqlite3.Error as err:
                msg(title='Error', style='critical', context=str(err))

    def add_new_entry(self):
        self.dialogNewEntry.exec()
        if self.dialogNewEntry.result() == QtWidgets.QDialog.Accepted:
            new_bibkey = self.dialogNewEntry.editBibkey.text()
            # check duplicate key.
            id_ = db_bibkey_id(self.cursor, new_bibkey)
            # if duplicate, there will be an id_, else None
            if isinstance(id_, type(None)):
                id_ = db_insert_new_bibkey(self.conn, self.cursor, new_bibkey)
                # before add new entry, ask if save the current one
                if self.mw.is_edited:
                    if q_save_entry(self):
                        self.save_entry()
                self.mw.clear_all()
                self.mw.new_bibkey(id_, new_bibkey)
            else:
                msg(title='Error', style='critical',
                    context='Bibkey already exists in database')
                # restart the dialog
                self.add_new_entry()

    def save_entry(self):
        entry_dict, tags = self.mw.getEntry()
        # check if bibkey is empty
        if entry_dict['bibkey']:
            # id_ = db_bibkey_id(self.cursor, entry_dict['bibkey'])
            # if id_:     # bibkey already exists
            try:
                db_update_entry(self.conn, self.cursor, entry_dict,
                                tags=tags)
                save_img_to_disk(entry_dict['img_pairs'])
                self.refresh_all_tags()
                # now everything is saved, restore edit status
                self.mw.is_edited = False
            except sqlite3.Error as err:
                msg(title='Error', style='critical', context=str(err))
            # else:
            #     try:
            #         db_insert_entry(self.conn, self.cursor, entry_dict,
            #                         tags=tags)
            #         self.refresh_all_tags()
            #         # now everything is saved, restore edit status
            #         self.mw.is_edited = False
            #     except sqlite3.Error as err:
            #         msg(title='Error', style='critical', context=str(err))
        else:
            self.dialogPatchKey.exec()

    def check_patchkey(self):
        patch_key = self.dialogPatchKey.inpKey.text().strip()
        if not patch_key:
            self.dialogPatchKey.reject()
        elif db_bibkey_id(self.cursor, patch_key):
            msg(title='Error', style='critical',
                context='Bibkey already exists in database. Use a new one')
            self.dialogPatchKey.reject()
        else:
            self.mw.inpBibKey.setText(patch_key)
            self.dialogPatchKey.accept()
            self.save_entry()

    def open_dialog_del_img(self):
        # need to first get the objects from current gpImage

        self.dialogDelImg.gpImage.load_imgs(self.mw.gpImage.get_list_img())
        self.dialogDelImg.exec()

    def del_img(self):
        checked_ids = self.dialogDelImg.gpImage.get_checked_img_ids()
        self.mw.gpImage.del_imgs(checked_ids)

    def view_img(self):
        self.dialogViewImg.load_imgs(self.mw.gpImage.get_list_img())
        self.dialogViewImg.showMaximized()

    def add_img(self):
        self.dialogAddImg.exec()
        if self.dialogAddImg.result() == QtWidgets.QDialog.Accepted:
            img = self.dialogAddImg.img
            if not img.isNull():
                self.mw.gpImage.add_sgl_img(img)
                # after image is inserted, clear the image in the dialog
                self.dialogAddImg.img = QImage()
                self.dialogAddImg.labelImg.clear()

    def search_bibkey(self):

        n_per_page = int(self.dialogBibKey.comboNPerPage.currentText())
        keyword = self.dialogBibKey.inpSearchWord.text().strip()
        try:
            bibkeys = db_search_bibkey(self.cursor, keyword, n_per_page, page=1)
            self.dialogBibKey.listEntry.clear()
            self.dialogBibKey.listEntry.addItems(bibkeys)
            self.dialogBibKey.listEntry.setCurrentRow(0)
            self.dialogBibKey.setCurrentPage(1)
        except sqlite3.Error as err:
            msg(title='Error', style='critical', context=str(err))

    def dialog_bibkey_next(self):
        n_per_page = int(self.dialogBibKey.comboNPerPage.currentText())
        keyword = self.dialogBibKey.inpSearchWord.text().strip()
        page = self.dialogBibKey.current_page + 1
        try:
            bibkeys = db_search_bibkey(self.cursor, keyword, n_per_page, page=page)
            if bibkeys:
                self.dialogBibKey.listEntry.clear()
                self.dialogBibKey.listEntry.addItems(bibkeys)
                self.dialogBibKey.listEntry.setCurrentRow(0)
                self.dialogBibKey.setCurrentPage(page)
            else:  # if returned bibkeys are empty, then it's the end of the
                # record, and therefore do not shift
                self.dialogBibKey.nextPage.setDisabled(True)
        except sqlite3.Error as err:
            msg(title='Error', style='critical', context=str(err))

    def dialog_bibkey_prev(self):
        n_per_page = int(self.dialogBibKey.comboNPerPage.currentText())
        keyword = self.dialogBibKey.inpSearchWord.text().strip()
        page = self.dialogBibKey.current_page - 1
        try:
            bibkeys = db_search_bibkey(self.cursor, keyword, n_per_page, page=page)
            self.dialogBibKey.listEntry.clear()
            self.dialogBibKey.listEntry.addItems(bibkeys)
            self.dialogBibKey.listEntry.setCurrentRow(0)
            self.dialogBibKey.setCurrentPage(page)
            self.dialogBibKey.nextPage.setDisabled(False)
        except sqlite3.Error as err:
            msg(title='Error', style='critical', context=str(err))

    def search_fulltext(self):
        field = self.dialogSearch.comboFields.currentText()
        genre = self.dialogSearch.comboGenre.currentText()
        keyword = self.dialogSearch.inpSearchWord.text()
        if keyword:
            selected_tags = self.dialogPickSearchTags.getSelectedTags()
            bibkeys = db_search_fulltext(self.cursor, field, genre, keyword,
                                         tags=selected_tags)
            self.dialogSearch.listEntry.clear()
            self.dialogSearch.listEntry.addItems(bibkeys)
            self.dialogSearch.listEntry.setCurrentRow(0)
        else:
            self.dialogSearch.listEntry.clear()

    def load_entry_fulltext(self):
        """  load an entry from fulltext search """
        # compare the current bibkey entry and the one to be loaded
        current_bibkey = self.mw.inpBibKey.text().strip()
        load_bibkey = self.dialogSearch.listEntry.currentItem().text()
        # do nothing, because the bibkey is already loaded
        if current_bibkey == load_bibkey:
            pass
        else:  # ask if need to save the current bibkey item
            if self.mw.is_edited:
                if q_save_entry(self):
                    self.save_entry()
            try:  # avoid query empty stuff
                bibkey = self.dialogSearch.listEntry.currentItem().text()
                a_dict, tags = db_select_entry(self.cursor, bibkey)
                self.mw.loadEntry(a_dict, tags)
                self.dialogPickDelTags.setTags(tags)
            except AttributeError:
                pass

    def load_entry_bibkey(self):
        """ load an entry from bibkey search """
        # compare the current bibkey entry and the one to be loaded
        current_bibkey = self.mw.inpBibKey.text().strip()
        load_bibkey = self.dialogBibKey.listEntry.currentItem().text()
        # do nothing, because the bibkey is already loaded
        if current_bibkey == load_bibkey:
            pass
        else:   # ask if need to save the current bibkey item
            if self.mw.is_edited:
                if q_save_entry(self):
                    self.save_entry()
            try:    # avoid query empty stuff
                bibkey = self.dialogBibKey.listEntry.currentItem().text()
                a_dict, tags = db_select_entry(self.cursor, bibkey)
                self.mw.loadEntry(a_dict, tags)
                self.dialogPickDelTags.setTags(tags)
            except AttributeError:
                pass


class DialogSearch(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(750)
        self.setWindowTitle('Search Entries')
        self.setWindowFlags(QtCore.Qt.Window)
        # put in in center of screen
        scr = QtWidgets.QApplication.desktop().screenGeometry()
        self.move(scr.center() - self.rect().center())

        self.btnSearch = QtWidgets.QPushButton('Search')
        self.comboFields = QtWidgets.QComboBox()
        self.comboFields.addItems(('All',) + FIELDS)
        self.comboFields.setFixedWidth(120)
        self.comboGenre = QtWidgets.QComboBox()
        self.comboGenre.addItems(('All',) + GENRES)
        self.comboGenre.setFixedWidth(120)
        self.btnSelTags = QtWidgets.QPushButton('all tags')
        self.btnSelTags.setFixedWidth(120)

        self.btnSearch.setFixedWidth(100)
        self.inpSearchWord = QtWidgets.QLineEdit()
        barLayout = QtWidgets.QGridLayout()
        barLayout.addWidget(QtWidgets.QLabel('Fields'), 0, 0)
        barLayout.addWidget(self.comboFields, 1, 0)
        barLayout.addWidget(QtWidgets.QLabel('Genre'), 0, 1)
        barLayout.addWidget(self.comboGenre, 1, 1)
        barLayout.addWidget(QtWidgets.QLabel('Tags'), 0, 2)
        barLayout.addWidget(self.btnSelTags, 1, 2)
        barLayout.addWidget(QtWidgets.QLabel('Search Word'), 0, 3)
        barLayout.addWidget(self.inpSearchWord, 1, 3)
        barLayout.addWidget(self.btnSearch, 1, 4)

        self.listEntry = QtWidgets.QListWidget()
        self.listEntry.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        self.btnLoad = QtWidgets.QPushButton('Load')
        self.btnClose = QtWidgets.QPushButton('Close')
        btnLayout = QtWidgets.QHBoxLayout()
        btnLayout.setAlignment(QtCore.Qt.AlignRight)
        btnLayout.addWidget(self.btnLoad)
        btnLayout.addWidget(self.btnClose)
        self.btnLoad.clicked.connect(self.accept)
        self.btnClose.clicked.connect(self.reject)

        thisLayout = QtWidgets.QVBoxLayout()
        thisLayout.setAlignment(QtCore.Qt.AlignTop)
        thisLayout.addLayout(barLayout)
        thisLayout.addWidget(self.listEntry)
        thisLayout.addLayout(btnLayout)
        self.setLayout(thisLayout)


class DialogBibKey(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Load bibkey entry')
        self.setWindowFlags(QtCore.Qt.Window)
        self.btnSearch = QtWidgets.QPushButton('Search')
        self.btnSearch.setFixedWidth(100)
        self.btnSearch.setShortcut(QtCore.Qt.Key_Return)
        self.inpSearchWord = QtWidgets.QLineEdit()
        self.resize(QtCore.QSize(400, 600))
        # put in in center of screen
        scr = QtWidgets.QApplication.desktop().screenGeometry()
        self.move(scr.center() - self.rect().center())
        barLayout = QtWidgets.QHBoxLayout()
        barLayout.addWidget(self.inpSearchWord)
        barLayout.addWidget(self.btnSearch)

        self.comboNPerPage = QtWidgets.QComboBox()
        self.comboNPerPage.addItems(['10', '20', '50', '100'])
        self.prevPage = QtWidgets.QPushButton('⏪')
        self.prevPage.setFixedWidth(30)
        self.nextPage = QtWidgets.QPushButton('⏩')
        self.nextPage.setFixedWidth(30)
        self.labelPage = QtWidgets.QLabel('Page ')
        self.current_page = 1
        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(QtWidgets.QLabel('# per page'))
        row1.addWidget(self.comboNPerPage)
        row1.addWidget(self.prevPage)
        row1.addWidget(self.labelPage)
        row1.addWidget(self.nextPage)
        self.listEntry = QtWidgets.QListWidget()
        self.listEntry.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        self.btnLoad = QtWidgets.QPushButton('Load')
        self.btnClose = QtWidgets.QPushButton('Close')
        btnLayout = QtWidgets.QHBoxLayout()
        btnLayout.setAlignment(QtCore.Qt.AlignRight)
        btnLayout.addWidget(self.btnLoad)
        btnLayout.addWidget(self.btnClose)
        self.btnLoad.clicked.connect(self.accept)
        self.btnClose.clicked.connect(self.reject)
        self.listEntry.itemDoubleClicked.connect(self.btnLoad.click)

        thisLayout = QtWidgets.QVBoxLayout()
        thisLayout.setAlignment(QtCore.Qt.AlignTop)
        thisLayout.addLayout(row1)
        thisLayout.addLayout(barLayout)
        thisLayout.addWidget(self.listEntry)
        thisLayout.addLayout(btnLayout)
        self.setLayout(thisLayout)

    def setCurrentPage(self, p):
        self.labelPage.setText('Page {:d}'.format(p))
        self.current_page = p
        self.prevPage.setDisabled(p <= 1)


class DialogViewImg(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('View Image')
        self.setWindowFlags(QtCore.Qt.Window)
        # put in in center of screen
        scr = QtWidgets.QApplication.desktop().screenGeometry()
        self.move(scr.center() - self.rect().center())
        self.btnPrev = QtWidgets.QPushButton(
                QIcon(path_join(ROOT, 'icon', 'img_prev.png')), '')
        self.btnNext = QtWidgets.QPushButton(
                QIcon(path_join(ROOT, 'icon', 'img_next.png')), '')
        self.btnPrev.setFixedWidth(40)
        self.btnNext.setFixedWidth(40)
        btnLayout = QtWidgets.QHBoxLayout()
        btnLayout.setAlignment(QtCore.Qt.AlignHCenter)
        btnLayout.addWidget(self.btnPrev)
        btnLayout.addWidget(self.btnNext)

        self._p = None
        self._current_idx = 0
        self._list_img = None
        self.labelImg = QtWidgets.QLabel()
        self.labelImg.setAlignment(QtCore.Qt.AlignHCenter |
                                   QtCore.Qt.AlignVCenter)
        area = QtWidgets.QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(self.labelImg)

        thisLayout = QtWidgets.QVBoxLayout()
        thisLayout.addLayout(btnLayout)
        thisLayout.addWidget(area)
        self.setLayout(thisLayout)

        self.btnPrev.clicked.connect(self.prev)
        self.btnNext.clicked.connect(self.next)

    def load_imgs(self, list_img):
        self._list_img = list_img
        if list_img:
            self._current_idx = 0
            self.show_img(list_img[0])
        else:
            self.labelImg.clear()

    def show_img(self, img):
        # get size of the image
        w = img.width()
        h = img.height()
        desk_w = QtWidgets.QApplication.desktop().width()
        desk_h = QtWidgets.QApplication.desktop().height()
        if w < (desk_w - 100) and h < (desk_h - 200):
            self.labelImg.setPixmap(QPixmap(img))
        else:
            self.labelImg.setPixmap(
                    QPixmap(img.scaled(desk_w - 100, desk_h - 200,
                                       QtCore.Qt.KeepAspectRatio)))

    def next(self):
        if self._list_img:
            if self._current_idx < len(self._list_img) - 1:
                self._current_idx += 1
                self.show_img(self._list_img[self._current_idx])
            else:
                self.show_img(self._list_img[-1])

    def prev(self):
        if self._list_img:
            if self._current_idx > 1:
                self._current_idx -= 1
                self.show_img(self._list_img[self._current_idx])
            else:
                self.show_img(self._list_img[0])


class DialogDelImg(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Delete Images')
        # put in in center of screen
        scr = QtWidgets.QApplication.desktop().screenGeometry()
        self.move(scr.center() - self.rect().center())

        self.btnDel = QtWidgets.QPushButton('Delete')
        self.btnCancel = QtWidgets.QPushButton('Cancel')
        self.btnDel.setFixedWidth(100)
        self.btnCancel.setFixedWidth(100)
        self.btnDel.clicked.connect(self.accept)
        self.btnCancel.clicked.connect(self.reject)
        btnLayout = QtWidgets.QHBoxLayout()
        btnLayout.setAlignment(QtCore.Qt.AlignRight)
        btnLayout.addWidget(self.btnDel)
        btnLayout.addWidget(self.btnCancel)

        self.gpImage = GroupImageInDialog(parent=self)
        area = QtWidgets.QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(self.gpImage)
        thisLayout = QtWidgets.QVBoxLayout()
        thisLayout.setAlignment(QtCore.Qt.AlignTop)
        thisLayout.addWidget(area)
        thisLayout.addLayout(btnLayout)
        self.setLayout(thisLayout)


class DialogPatchBibkey(QtWidgets.QDialog):
    """ Prevent user to save with blank bibkey"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add a bibkey')
        # put in in center of screen
        scr = QtWidgets.QApplication.desktop().screenGeometry()
        self.move(scr.center() - self.rect().center())

        label = QtWidgets.QLabel('Current entry cannot be saved without a valid'
                                 'bibkey. Please input the bibkey here!')
        self.inpKey = QtWidgets.QLineEdit()
        self.btnOk = QtWidgets.QPushButton('Ok')
        thisLayout = QtWidgets.QVBoxLayout()
        thisLayout.addWidget(label)
        thisLayout.addWidget(self.inpKey)
        thisLayout.addWidget(self.btnOk)
        self.setLayout(thisLayout)

    def reject(self):
        """ Forbid user from closing of the dialog window until a valid bibkey
        is entered. """
        pass


class DialogNewEntry(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.setWindowTitle('Insert New Entry')
        # put in in center of screen
        scr = QtWidgets.QApplication.desktop().screenGeometry()
        self.move(scr.center() - self.rect().center())

        self.editBibkey = QtWidgets.QLineEdit()
        self.btnOk = QtWidgets.QPushButton('Insert')
        self.btnCancel = QtWidgets.QPushButton('Cancel')
        row1 = QtWidgets.QHBoxLayout()
        row1.setAlignment(QtCore.Qt.AlignLeft)
        row1.addWidget(QtWidgets.QLabel('Bibkey'))
        row1.addWidget(self.editBibkey)
        row2 = QtWidgets.QHBoxLayout()
        row2.setAlignment(QtCore.Qt.AlignRight)
        row2.addWidget(self.btnCancel)
        row2.addWidget(self.btnOk)
        thisLayout = QtWidgets.QVBoxLayout()
        thisLayout.setAlignment(QtCore.Qt.AlignTop)
        thisLayout.addLayout(row1)
        thisLayout.addLayout(row2)
        self.setLayout(thisLayout)
        self.btnOk.clicked.connect(self.accept)
        self.btnCancel.clicked.connect(self.reject)


class DialogChangeBibkey(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.setWindowTitle('Change Current Bibkey')
        # put in in center of screen
        scr = QtWidgets.QApplication.desktop().screenGeometry()
        self.move(scr.center() - self.rect().center())

        self.oldBibkey = QtWidgets.QLineEdit()
        self.oldBibkey.setReadOnly(True)
        self.editNewBibkey = QtWidgets.QLineEdit()
        self.btnOk = QtWidgets.QPushButton('Update')
        self.btnCancel = QtWidgets.QPushButton('Cancel')
        row1 = QtWidgets.QHBoxLayout()
        row1.setAlignment(QtCore.Qt.AlignLeft)
        row1.addWidget(QtWidgets.QLabel('Old Bibkey'))
        row1.addWidget(self.oldBibkey)
        row2 = QtWidgets.QHBoxLayout()
        row2.setAlignment(QtCore.Qt.AlignLeft)
        row2.addWidget(QtWidgets.QLabel('New Bibkey'))
        row2.addWidget(self.editNewBibkey)
        row3 = QtWidgets.QHBoxLayout()
        row3.setAlignment(QtCore.Qt.AlignRight)
        row3.addWidget(self.btnOk)
        row3.addWidget(self.btnCancel)
        thisLayout = QtWidgets.QVBoxLayout()
        thisLayout.setAlignment(QtCore.Qt.AlignTop)
        thisLayout.addLayout(row1)
        thisLayout.addLayout(row2)
        thisLayout.addLayout(row3)
        self.setLayout(thisLayout)
        self.btnOk.clicked.connect(self.accept)
        self.btnCancel.clicked.connect(self.reject)


class DialogAddImg(QtWidgets.QDialog):

    def __init__(self, clipboard, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(400)
        self.setWindowTitle('Add Image')
        # put in in center of screen
        scr = QtWidgets.QApplication.desktop().screenGeometry()
        self.move(scr.center() - self.rect().center())

        self._clipboard = clipboard
        self.img = QImage()
        self.labelImg = QtWidgets.QLabel()
        self.btnOk = QtWidgets.QPushButton('Add')
        self.btnCancel = QtWidgets.QPushButton('Cancel')
        rowBtn = QtWidgets.QHBoxLayout()
        rowBtn.setAlignment(QtCore.Qt.AlignRight)
        rowBtn.addWidget(self.btnCancel)
        rowBtn.addWidget(self.btnOk)
        thisLayout = QtWidgets.QVBoxLayout()
        thisLayout.addWidget(self.labelImg)
        thisLayout.addLayout(rowBtn)
        self.setLayout(thisLayout)
        self.btnOk.clicked.connect(self.accept)
        self.btnCancel.clicked.connect(self.reject)

    def keyPressEvent(self, ev):
        if ev.key() == QtCore.Qt.Key_V and ev.modifiers() == QtCore.Qt.ControlModifier:
            self.img = self._clipboard.image()
            self.labelImg.setPixmap(
                    QPixmap(self.img.scaled(400, 400, QtCore.Qt.KeepAspectRatio)))
            ev.accept()
        elif ev.key() == QtCore.Qt.Key_Escape:
            self.reject()
        else:
            ev.accept()


class MainWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.is_edited = False
        self._entry_id = 0
        self.inpBibKey = QtWidgets.QLineEdit()
        self.inpBibKey.setDisabled(True)    # only for display, can't edit directly
        self.btnChangeBibkey = QtWidgets.QPushButton('Update Bibkey')
        self.tagBox = TagBox(parent=self)
        self.editTitle = QtWidgets.QTextEdit()
        self.editTitle.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.editTitle.setWordWrapMode(QTextOption.WordWrap)
        self.editAuthor = QtWidgets.QTextEdit()
        self.editAuthor.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.editAuthor.setWordWrapMode(QTextOption.WordWrap)
        self.comboGenre = QtWidgets.QComboBox()
        self.comboGenre.addItems(GENRES)
        self.comboGenre.setFixedWidth(120)
        self.editThesis = QtWidgets.QTextEdit()
        self.editThesis.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.editThesis.setWordWrapMode(QTextOption.WordWrap)
        self.editHypo = QtWidgets.QTextEdit()
        self.editHypo.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.editHypo.setWordWrapMode(QTextOption.WordWrap)
        self.editMethod = QtWidgets.QTextEdit()
        self.editMethod.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.editMethod.setWordWrapMode(QTextOption.WordWrap)
        self.editFinding = QtWidgets.QTextEdit()
        self.editFinding.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.editFinding.setWordWrapMode(QTextOption.WordWrap)
        self.editComment = QtWidgets.QTextEdit()
        self.editComment.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.editComment.setWordWrapMode(QTextOption.WordWrap)
        self.gpImage = GroupImage(parent=self)

        areaTitle = QtWidgets.QScrollArea()
        areaTitle.setWidgetResizable(True)
        areaTitle.setWidget(self.editTitle)
        areaAuthor = QtWidgets.QScrollArea()
        areaAuthor.setWidgetResizable(True)
        areaAuthor.setWidget(self.editAuthor)
        areaThesis = QtWidgets.QScrollArea()
        areaThesis.setWidgetResizable(True)
        areaThesis.setWidget(self.editThesis)
        areaHypo = QtWidgets.QScrollArea()
        areaHypo.setWidgetResizable(True)
        areaHypo.setWidget(self.editHypo)
        areaMethod = QtWidgets.QScrollArea()
        areaMethod.setWidgetResizable(True)
        areaMethod.setWidget(self.editMethod)
        areaFinding = QtWidgets.QScrollArea()
        areaFinding.setWidgetResizable(True)
        areaFinding.setWidget(self.editFinding)
        areaComment = QtWidgets.QScrollArea()
        areaComment.setWidgetResizable(True)
        areaComment.setWidget(self.editComment)
        areaImg = QtWidgets.QScrollArea()
        areaImg.setWidgetResizable(True)
        areaImg.setWidget(self.gpImage)

        topLayout = QtWidgets.QHBoxLayout()
        topLayout.addWidget(QtWidgets.QLabel('Genre'))
        topLayout.addWidget(self.comboGenre)
        topLayout.addWidget(QtWidgets.QLabel('Bibkey'))
        topLayout.addWidget(self.inpBibKey)
        topLayout.addWidget(self.btnChangeBibkey)
        topLayout.setAlignment(QtCore.Qt.AlignLeft)

        thisLayout = QtWidgets.QGridLayout()
        thisLayout.setAlignment(QtCore.Qt.AlignTop)
        thisLayout.addLayout(topLayout, 0, 0, 1, 4)
        thisLayout.addWidget(self.tagBox, 1, 0, 1, 4)
        thisLayout.addWidget(QtWidgets.QLabel('Title'), 2, 0)
        thisLayout.addWidget(QtWidgets.QLabel('Thesis & Objective'), 2, 1)
        thisLayout.addWidget(QtWidgets.QLabel('Theory & Hypothesis'), 2, 2)
        thisLayout.addWidget(areaTitle, 3, 0)
        thisLayout.addWidget(QtWidgets.QLabel('Author'), 4, 0)
        thisLayout.addWidget(areaAuthor, 5, 0)
        thisLayout.addWidget(areaThesis, 3, 1, 3, 1)
        thisLayout.addWidget(areaHypo, 3, 2, 3, 1)
        thisLayout.addWidget(QtWidgets.QLabel('Method & Tech'), 6, 0)
        thisLayout.addWidget(QtWidgets.QLabel('Result & Finding'), 6, 1)
        thisLayout.addWidget(QtWidgets.QLabel('Comment'), 6, 2)
        thisLayout.addWidget(areaMethod, 7, 0)
        thisLayout.addWidget(areaFinding, 7, 1)
        thisLayout.addWidget(areaComment, 7, 2)
        thisLayout.addWidget(QtWidgets.QLabel('Images'), 2, 3)
        thisLayout.addWidget(areaImg, 3, 3, 5, 1)
        thisLayout.setRowStretch(3, 1)
        thisLayout.setRowStretch(5, 1)
        thisLayout.setRowStretch(7, 2)
        self.setLayout(thisLayout)

        self.editTitle.textChanged.connect(self.edit_status)
        self.editAuthor.textChanged.connect(self.edit_status)
        self.editThesis.textChanged.connect(self.edit_status)
        self.editHypo.textChanged.connect(self.edit_status)
        self.editMethod.textChanged.connect(self.edit_status)
        self.editFinding.textChanged.connect(self.edit_status)
        self.editComment.textChanged.connect(self.edit_status)
        self.tagBox.btnAdd.clicked.connect(self.edit_status)
        self.tagBox.btnDel.clicked.connect(self.edit_status)
        self.inpBibKey.textChanged.connect(self.edit_status)
        self.comboGenre.currentIndexChanged.connect(self.edit_status)
        self.gpImage.sig_img_changed.connect(self.edit_status)
        self.gpImage.img_width = int(self.gpImage.width() -
                                     areaImg.verticalScrollBar().width() * 2)

    def edit_status(self):
        """ If anything changes in the box, trigger this to write the edit status
        """
        self.is_edited = True

    def new_bibkey(self, id_, bibkey):
        self._entry_id = id_
        self.gpImage._entry_id = id_
        self.inpBibKey.setText(bibkey)

    def clear_all(self):
        """ Clear all contents """
        self._entry_id = 0
        self.editTitle.clear()
        self.editThesis.clear()
        self.editComment.clear()
        self.editHypo.clear()
        self.editFinding.clear()
        self.editMethod.clear()
        self.editAuthor.clear()
        self.gpImage.clear()
        self.tagBox.dispTags.setTags([])

    def getEntry(self):
        """ Get entry information """
        a_dict = {
            'id': self._entry_id,
            'bibkey': self.inpBibKey.text().strip(),
            'genre': self.comboGenre.currentText(),
            'title': self.editTitle.toPlainText(),
            'author': self.editAuthor.toPlainText(),
            'thesis': self.editThesis.toPlainText(),
            'hypothesis': self.editHypo.toPlainText(),
            'method': self.editMethod.toPlainText(),
            'finding': self.editFinding.toPlainText(),
            'comment': self.editComment.toPlainText(),
            'img_linkstr': self.gpImage.get_link_str(),
            'img_pairs': zip(self.gpImage.get_link_str(),
                             self.gpImage.get_list_img())
        }
        tags = self.tagBox.dispTags.tags()
        return a_dict, tags

    def loadEntry(self, a_dict, tags):
        """ Load entry information """
        self._entry_id = a_dict['id']
        self.inpBibKey.setText(a_dict['bibkey'])
        self.comboGenre.setCurrentText(a_dict['genre'])
        self.editTitle.setText(a_dict['title'])
        self.editAuthor.setText(a_dict['author'])
        self.editThesis.setText(a_dict['thesis'])
        self.editHypo.setText(a_dict['hypothesis'])
        self.editMethod.setText(a_dict['method'])
        self.editFinding.setText(a_dict['finding'])
        self.editComment.setText(a_dict['comment'])
        self.gpImage.load_imgs_from_disk(a_dict['img_linkstr'])
        self.tagBox.dispTags.setTags(tags)
        # new entry loaded, reset edit status
        self.is_edited = False


class GroupImageInDialog(QtWidgets.QWidget):
    """ Group image widget in delete dialog. Has accompanied checkboxes """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QtWidgets.QFormLayout()
        self._list_rows = []    # [(ckbox, qlabel)]
        self.setLayout(self._layout)

    def load_imgs(self, list_img):
        n_new = len(list_img)
        n_old = len(self._list_rows)
        if n_new > n_old:
            for row, img in zip(self._list_rows, list_img[:n_old]):
                ckbox, qlabel = row
                ckbox.setChecked(0)
                qlabel.setPixmap(QPixmap(img.scaledToWidth(300)))
            for img in list_img[n_old:]:
                ckbox = QtWidgets.QCheckBox()
                qlabel = QtWidgets.QLabel()
                qlabel.setPixmap(QPixmap(img.scaledToWidth(300)))
                self._list_rows.append((ckbox, qlabel))
                self._layout.addRow(ckbox, qlabel)
        else:
            for row, img in zip(self._list_rows[:n_new], list_img):
                ckbox, qlabel = row
                ckbox.setChecked(0)
                qlabel.setPixmap(QPixmap(img.scaledToWidth(300)))
            for i in range(n_new, n_old):
                ckbox, qlabel = self._list_rows.pop()
                self._layout.removeWidget(ckbox)
                self._layout.removeWidget(qlabel)
                ckbox.deleteLater()
                qlabel.deleteLater()

    def get_checked_img_ids(self):
        checked_img_ids = []
        for i, row in enumerate(self._list_rows):
            if row[0].isChecked():
                checked_img_ids.append(i)
        return checked_img_ids


class GroupImage(QtWidgets.QWidget):

    sig_img_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self._list_img = []
        self._list_wdgs = []
        self._list_links = []
        self._entry_id = 0
        self.setLayout(self._layout)
        self.img_width = 100

    def load_imgs_from_disk(self, img_links):

        if img_links:
            self._list_links = img_links.split(',')
        else:
            self._list_links = []
        n_new = len(self._list_links)
        n_old = len(self._list_wdgs)
        if n_new > n_old:
            for img, wdg, link in zip(self._list_img, self._list_wdgs,
                                      self._list_links[:n_old]):
                img.load(path_join(ROOT, 'img', link))
                wdg.setPixmap(QPixmap(img.scaledToWidth(self.img_width)))
            for link in self._list_links[n_old:]:
                wdg = QtWidgets.QLabel()
                img = QImage(path_join(ROOT, 'img', link))
                wdg.setPixmap(QPixmap(img.scaledToWidth(self.img_width)))
                self._list_wdgs.append(wdg)
                self._list_img.append(img)
                self._layout.addWidget(wdg)
        else:
            for img, wdg, link in zip(self._list_img, self._list_wdgs[:n_new],
                                      self._list_links):
                img.load(path_join(ROOT, 'img', link))
                wdg.setPixmap(QPixmap(img.scaledToWidth(self.img_width)))
            for i in range(n_new, n_old):
                self._list_img.pop()
                wdg = self._list_wdgs.pop()
                self._layout.removeWidget(wdg)
                wdg.deleteLater()
        self.adjustSize()

    def add_sgl_img(self, img):
        """ add single image """
        wdg = QtWidgets.QLabel()
        wdg.setPixmap(QPixmap(img.scaledToWidth(self.img_width)))
        self._list_img.append(img)
        self._list_links.append(
            'ID_{:4>d}_{:d}.png'.format(self._entry_id, img.cacheKey())
        )
        self._list_wdgs.append(wdg)
        self._layout.addWidget(wdg)
        self.adjustSize()
        self.sig_img_changed.emit()

    def del_imgs(self, checked_ids):

        # sort checked id
        checked_ids.sort()
        checked_ids.reverse()
        # go through list reversely to pop corresponding elements
        for id_ in checked_ids:
            self._list_img.pop(id_)
            link = self._list_links.pop(id_)
            wdg = self._list_wdgs.pop(id_)
            self._layout.removeWidget(wdg)
            wdg.deleteLater()
            fillename = path_join(ROOT, 'img', link)
            if isfile(fillename):
                os_remove(fillename)
            self.sig_img_changed.emit()

    def clear(self):
        while self._list_wdgs:
            wdg = self._list_wdgs.pop()
            wdg.deleteLater()
        self._list_links = []
        self._list_img = []

    def get_link_str(self):
        """ return the image links """
        return ','.join(self._list_links)

    def get_list_img(self):
        return self._list_img


class MenuBar(QtWidgets.QMenuBar):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.actionNewEntry = QtWidgets.QAction('Insert New Entry')
        self.actionNewEntry.setShortcut('Ctrl+N')
        self.actionSaveEntry = QtWidgets.QAction('Save Current Entry')
        self.actionSaveEntry.setShortcut('Ctrl+S')
        self.actionAddImg = QtWidgets.QAction('Add Image')
        self.actionAddImg.setShortcut('Ctrl+I')
        self.actionViewImg = QtWidgets.QAction('View Image')
        self.actionDeleteImg = QtWidgets.QAction('Delete Image')
        self.actionSearchBibkey = QtWidgets.QAction('Search Bibkey')
        self.actionSearchBibkey.setShortcut('Ctrl+H')
        self.actionSearchDoc = QtWidgets.QAction('Fulltext Search')
        self.actionSearchDoc.setShortcut('Alt+H')

        menuEntry = self.addMenu('&Entry')
        menuEntry.addAction(self.actionNewEntry)
        menuEntry.addAction(self.actionSaveEntry)
        menuEntry.addSeparator()
        menuEntry.addAction(self.actionAddImg)
        menuEntry.addAction(self.actionViewImg)
        menuEntry.addAction(self.actionDeleteImg)

        menuSearch = self.addMenu('&Search')
        menuSearch.addAction(self.actionSearchBibkey)
        menuSearch.addAction(self.actionSearchDoc)


class ToolBar(QtWidgets.QToolBar):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.actionNewEntry = QtWidgets.QAction(
                QIcon(path_join(ROOT, 'icon', 'new_entry.png')), 'Insert New Entry')
        self.actionSaveEntry = QtWidgets.QAction(
                QIcon(path_join(ROOT, 'icon', 'save_entry.png')), 'Save Current Entry')
        self.actionAddImg = QtWidgets.QAction(
                QIcon(path_join(ROOT, 'icon', 'add_img.png')), 'Add Image')
        self.actionViewImg = QtWidgets.QAction(
                QIcon(path_join(ROOT, 'icon', 'view_img.png')), 'View Image')
        self.actionDeleteImg = QtWidgets.QAction(
                QIcon(path_join(ROOT, 'icon', 'del_img.png')), 'Delete Image')
        self.actionSearchBibkey = QtWidgets.QAction(
                QIcon(path_join(ROOT, 'icon', 'search.png')), 'Search Bibkey')
        self.actionSearchDoc = QtWidgets.QAction(
                QIcon(path_join(ROOT, 'icon', 'search_doc.png')), 'Fulltext Search')

        self.addAction(self.actionNewEntry)
        self.addAction(self.actionSaveEntry)
        self.addSeparator()
        self.addAction(self.actionAddImg)
        self.addAction(self.actionViewImg)
        self.addAction(self.actionDeleteImg)
        self.addSeparator()
        self.addAction(self.actionSearchBibkey)
        self.addAction(self.actionSearchDoc)
        self.setMovable(False)
        self.setIconSize(QtCore.QSize(40, 40))


class TagLabel(QtWidgets.QLabel):
    """ Reimplement QLable to display tags """

    def __init__(self, color, title='', parent=None):
        super().__init__(parent)
        self.setText(title)
        self.setStyleSheet("""border-style: solid;
                              border-width: 2px;
                              border-radius: 4px;
                              border-color: {:s};
                              padding: 1px;
                           """.format(color))


class TagBtn(QtWidgets.QPushButton):
    """ Reimplement toggled button to display selected tags """

    def __init__(self, color, title='', parent=None):
        super().__init__(parent)

        self._color = color
        self.setText(title)
        self.setCheckable(True)
        self.setChecked(False)
        self.setStatus(False)
        self.toggled[bool].connect(self.setStatus)

    def setStatus(self, b):
        """ Set color by bool """

        if b:    # toggled
            self.setStyleSheet("""border-style: solid;
                                  border-width: 2px;
                                  border-radius: 4px;
                                  border-color: {:s};
                                  padding: 1px;
                               """.format(self._color))
        else:   # untoggled
            self.setStyleSheet("""border-style: none;
                                  padding: 3px;
                               """)


class TagBox(QtWidgets.QWidget):
    """ Custom widget to hold tag addition / removal in the main GUI """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.btnAdd = QtWidgets.QPushButton('Add Tag')
        self.btnDel = QtWidgets.QPushButton('Remove Tag')
        self.comboTags = QtWidgets.QComboBox()
        self.editNewTag = QtWidgets.QLineEdit()
        self.comboTags.setLineEdit(self.editNewTag)
        self.dispTags = DispTags1Row(COLOR_BLUE, parent=self)

        thisLayout = QtWidgets.QHBoxLayout()
        thisLayout.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        thisLayout.addWidget(self.comboTags)
        thisLayout.addWidget(self.btnAdd)
        thisLayout.addWidget(self.btnDel)
        thisLayout.addWidget(self.dispTags)
        self.setLayout(thisLayout)


class DispTags1Row(QtWidgets.QWidget):
    """ 1-row widget to display tags. no interaction """

    def __init__(self, color, parent=None):
        super().__init__(parent)

        self._color = color
        self._layout = QtWidgets.QGridLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setAlignment(QtCore.Qt.AlignLeft)
        self.setLayout(self._layout)
        self._list_widgets = []

    def setTags(self, tags):

        n_tag = len(tags)
        n_wdg = len(self._list_widgets)
        if n_tag > n_wdg:
            for tag, wdg in zip(tags[:n_wdg], self._list_widgets):
                wdg.setText(tag)
            for i, tag in enumerate(tags[n_wdg:]):
                wdg = TagLabel(self._color, title=tag)
                self._list_widgets.append(wdg)
                self._layout.addWidget(wdg, 0, i+n_wdg)
        else:
            for tag, wdg in zip(tags, self._list_widgets[:n_tag]):
                wdg.setText(tag)
            for i in range(n_tag, n_wdg):
                wdg = self._list_widgets.pop()
                self._layout.removeWidget(wdg)
                wdg.deleteLater()

    def addTag(self, tag):
        """ Add one tag """
        if tag not in self.tags():  # avoid duplicates
            wdg = TagLabel(self._color, title=tag)
            self._layout.addWidget(wdg, 0, self._layout.columnCount())
            self._list_widgets.append(wdg)

    def tags(self):
        return list(wdg.text() for wdg in self._list_widgets)


class DialogMultiTag(QtWidgets.QDialog):
    """ Dialog window for multiple selection of tags """

    cols = 5     # 5 tags in 1 column

    def __init__(self, color='#0066cc', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select Tags')
        self.setMinimumWidth(500)

        self._color = color
        self._list_widgets = []
        self._layout = QtWidgets.QGridLayout()
        self._layout.setAlignment(QtCore.Qt.AlignTop)
        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(self._layout)

        area = QtWidgets.QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(central_widget)

        btnBox = QtWidgets.QDialogButtonBox()
        btnBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        btnBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        btnBox.addButton(QtWidgets.QDialogButtonBox.Reset)

        thisLayout = QtWidgets.QVBoxLayout()
        thisLayout.setAlignment(QtCore.Qt.AlignTop)
        thisLayout.addWidget(area)
        thisLayout.addWidget(btnBox)
        self.setLayout(thisLayout)

        btnBox.accepted.connect(self.accept)
        btnBox.rejected.connect(self.reject)
        btnBox.clicked[QtWidgets.QAbstractButton].connect(self.reset)

    def reset(self, obj):
        if obj.text() == 'Reset':
            for wdg in self._list_widgets:
                wdg.setChecked(False)

    def setTags(self, tags):

        n_tag = len(tags)
        n_wdg = len(self._list_widgets)
        if n_tag > n_wdg:
            for tag, wdg in zip(tags[:n_wdg], self._list_widgets):
                wdg.setText(tag)
            for i, tag in enumerate(tags[n_wdg:]):
                wdg = TagBtn(self._color, title=tag)
                self._list_widgets.append(wdg)
                row = (i + n_wdg) // self.cols
                col = (i + n_wdg) % self.cols
                self._layout.addWidget(wdg, row, col)
        else:
            for tag, wdg in zip(tags, self._list_widgets[:n_tag]):
                wdg.setText(tag)
            for i in range(n_tag, n_wdg):
                wdg = self._list_widgets.pop()
                self._layout.removeWidget(wdg)
                wdg.deleteLater()

    def getSelectedTags(self):

        a_list = []
        for wdg in self._list_widgets:
            if wdg.isChecked():
                a_list.append(wdg.text())
        return a_list

    def getSelectedNum(self):
        i = 0
        for wdg in self._list_widgets:
            if wdg.isChecked():
                i += 1
        return i


def msg(title='', context='', style=''):
    """ Pop up a message box for information / warning
    :argument
        parent: QWiget          parent QWiget
        title: str              title string
        context: str            context string
        style: str              style of message box
            'info'              information box
            'warning'           warning box
            'critical'          critical box
    """

    if style == 'info':
        d = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Information, title, context)
    elif style == 'warning':
        d = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, title, context)
    elif style == 'critical':
        d = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, title, context)
    else:
        d = QtWidgets.QMessageBox(QtWidgets.QMessageBox.NoIcon, title, context)
    d.exec_()


def q_save_entry(obj):
    context = 'Save the current entry content?'
    q = QtWidgets.QMessageBox.question(obj, 'Save?', context,
                                       QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                       QtWidgets.QMessageBox.Yes)
    return q == QtWidgets.QMessageBox.Yes


def launch():
   
    app = QtWidgets.QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
    

def create_or_open_db(filename):
    """ Create (1st time) or open database
    :argument:
        filename: str           database file
    :returns:
        conn: sqlite3 database connection
        cursor: sqlite3 database cursor
    """

    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    sql = """ CREATE TABLE IF NOT EXISTS note (
        id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        bibkey TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL, 
        author TEXT NOT NULL,
        genre TEXT, 
        thesis TEXT, 
        hypothesis TEXT,
        method TEXT,
        finding TEXT, 
        comment TEXT,
        img_linkstr TEXT
    );"""
    cursor.execute(sql)
    
    sql = """ CREATE TABLE IF NOT EXISTS tags (
        keyid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        id INTEGER NOT NULL,
        bibkey TEXT NOT NULL,
        tag TEXT NOT NULL
    );"""
    cursor.execute(sql)

    # create fts5 virtual table for full text search
    sql = """ CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
        title,
        author,
        thesis, 
        hypothesis,
        method, 
        finding, 
        comment,
        content="note",
        content_rowid="id"
    );
    """
    cursor.execute(sql)

    # create triggers
    cursor.execute(""" CREATE TRIGGER IF NOT EXISTS tbl_ai 
    AFTER INSERT ON note BEGIN
    INSERT INTO fts(rowid, title, author, thesis, hypothesis, method, 
        finding, comment) VALUES (new.id, new.title, new.author, new.thesis, 
        new.hypothesis, new.method, new.finding, new.comment);
    END;""")
    cursor.execute(""" CREATE TRIGGER IF NOT EXISTS tbl_ad 
    AFTER DELETE ON note BEGIN
      INSERT INTO fts(fts, rowid, title, author, thesis, hypothesis, method, 
        finding, comment) VALUES ('delete', old.id, old.title, old.author, old.thesis, 
        old.hypothesis, old.method, old.finding, old.comment);
    END;""")
    cursor.execute(""" CREATE TRIGGER IF NOT EXISTS tbl_au 
    AFTER UPDATE ON note BEGIN
      INSERT INTO fts(fts, rowid, title, author, thesis, hypothesis, method, 
        finding, comment) VALUES ('delete', old.id, old.title, old.author, old.thesis, 
        old.hypothesis, old.method, old.finding, old.comment);
      INSERT INTO fts(rowid, title, author, thesis, hypothesis, method, 
        finding, comment) VALUES (new.id, new.title, new.author, new.thesis, 
        new.hypothesis, new.method, new.finding, new.comment);
    END;""")

    conn.commit()

    return conn, cursor


def db_insert_new_bibkey(conn, c, bibkey):
    """ Insert new bibkey (and create entry)
    :argument
        conn:           db connection
        c:              db cursor
        bibkey: str     new bibkey
    :returns
        id_: int        new entry id
    """
    # title & author are not null, so need to give some default value
    c.execute("INSERT INTO note (bibkey, title, author) VALUES (?, ?, ?)",
              (bibkey, ' ', ' '))
    conn.commit()
    return db_bibkey_id(c, bibkey)


def db_insert_entry(conn, c, entry_dict, tags=None):
    """ Insert new entry into database """

    fields = ['bibkey', 'title', 'author', 'genre', 'thesis', 'hypothesis',
              'method', 'finding', 'comment', 'img_linkstr']
    sql = """ INSERT INTO note ({:s}) VALUES (?,?,?,?,?,?,?,?,?,?) 
            """.format(','.join(fields))
    c.execute(sql, tuple(entry_dict[field] for field in fields))
    conn.commit()

    # get id
    id_ = db_bibkey_id(c, entry_dict['bibkey'])
    if tags:
        sql = """ INSERT INTO tags (id, bibkey, tag) 
        VALUES ({:d}, {:s}, ?) """.format(id_, entry_dict['bibkey'])
        c.executemany(sql, ((tag,) for tag in tags))
        conn.commit()


def db_update_entry(conn, c, entry_dict, tags=None):
    """ Update entry in database """

    id_ = entry_dict['id']
    fields = ['author', 'title', 'genre', 'thesis', 'hypothesis',
              'method', 'finding', 'comment', 'img_linkstr']
    sql = """ UPDATE note SET {:s} WHERE id = (?) 
            """.format(','.join('{:s} = (?)'.format(field) for field in fields))
    c.execute(sql, tuple(list(entry_dict[field] for field in fields) + [id_]))
    conn.commit()

    c.execute("SELECT tag FROM tags WHERE id = (?)", (id_, ))
    old_tags = list(x[0] for x in c.fetchall())
    # add the rest of new tags
    for tag in tags:
        if tag in old_tags:
            pass
        else:
            c.execute('INSERT INTO tags (id, bibkey, tag) VALUES (?, ?, ?)',
                      (id_, entry_dict['bibkey'], tag))
    # remove old tags that do not exist in tags any more
    for old_tag in old_tags:
        if old_tag in tags:
            # old tag still exist, keep
            pass
        else:
            c.execute("DELETE FROM tag WHERE id = (?) AND tag = (?)",
                      (id_, old_tag))
    conn.commit()


def db_replace_bibkey(conn, c, old_key, new_key):
    """ Replace old bibkey with new bibkey """
    id_ = db_bibkey_id(c, old_key)
    sql = 'UPDATE note SET bibkey = (?) WHERE id = (?)'
    c.execute(sql, (new_key, id_))
    sql = 'UPDATE tags SET bibkey = (?) WHERE id = (?)'
    c.execute(sql, (new_key, id_))
    conn.commit()


def db_bibkey_id(c, bibkey):
    """ Return the id of tbe bibkey. Reture None if not found """
    c.execute('SELECT id FROM note WHERE bibkey = (?)', (bibkey,))
    res = c.fetchall()
    if res:
        return res[0][0]
    else:
        return None


def db_select_last_entry(c):
    """ Seletc the last entry from database """
    fields = ['id', 'bibkey', 'title', 'author', 'genre', 'thesis',
              'hypothesis', 'method', 'finding', 'comment', 'img_linkstr']
    sql = "SELECT {:s} FROM note ORDER BY id DESC LIMIT 1".format(','.join(fields))
    c.execute(sql)
    result = c.fetchall()
    a_dict = {}
    if result:
        for field, value in zip(fields, result[0]):
            a_dict[field] = value
    else:
        for field in fields:
            a_dict[field] = ''

    # get tags
    if a_dict:
        c.execute("SELECT tag FROM tags WHERE id = (?) ORDER BY tag ASC",
                  (a_dict['id'], ))
        tags = tuple(r[0] for r in c.fetchall())
    else:
        tags = ()

    return a_dict, tags


def db_select_entry(c, bibkey):
    """ Select entry from database
    :argument
        c: sqlite3 cursor
    :returns
        entry_dict: dict
    """
    fields = ['id', 'bibkey', 'title', 'author', 'genre', 'thesis',
              'hypothesis', 'method', 'finding', 'comment', 'img_linkstr']
    sql = "SELECT {:s} FROM note WHERE bibkey = (?)".format(','.join(fields))
    c.execute(sql, (bibkey,))
    result = c.fetchall()[0]
    a_dict = {}
    for field, value in zip(fields, result):
        a_dict[field] = value
    c.execute("SELECT tag FROM tags WHERE id = (?) ORDER BY tag ASC",
              (a_dict['id'],))
    tags = tuple(r[0] for r in c.fetchall())
    return a_dict, tags


def db_query_all_tags(c):
    """ Query all tags """

    c.execute("SELECT DISTINCT tag FROM tags ORDER BY tag COLLATE NOCASE ASC")
    return tuple(r[0] for r in c.fetchall())


def db_search_fulltext(c, field, genre, keyword, tags=None):
    """ Query bibkeys that matches fields with keyword
    :argument
        c: sqlite3 cursor
        field: str
        genre: str
        keyword: str
        tags: list of strings
    :returns
        bibkeys: list of matched bibkeys
    """
    if genre == 'All':
        genre_cond = ''
    else:
        genre_cond = " genre = '{:s}' AND ".format(genre)

    if tags:
        tag_str = ", ".join(list("'{:s}'".format(t) for t in tags))
        if field == 'All':
            all_fields = '{title author thesis hypothesis method finding comment}'
            sql = """ SELECT DISTINCT note.bibkey FROM note 
            JOIN tags ON note.bibkey = tags.bibkey
            WHERE {:s} id IN 
            (SELECT rowid FROM fts WHERE fts MATCH '{:s}: {:s}' ORDER BY RANK DESC)
            AND tags.tag IN ({:s})
            ORDER BY note.bibkey ASC
            """.format(genre_cond, all_fields, keyword, tag_str)
        else:
            sql = """ SELECT DISTINCT note.bibkey FROM note
            JOIN tags ON note.bibkey = tags.bibkey 
            WHERE {:s} id IN 
            (SELECT rowid FROM fts WHERE {:s} MATCH '{:s}' ORDER BY RANK DESC)
            AND tags.tag IN ({:s})
            ORDER BY note.bibkey ASC
            """.format(genre_cond, field, keyword, tag_str)
    else:
        if field == 'All':
            all_fields = '{title author thesis hypothesis method finding comment}'
            sql = """ SELECT bibkey FROM note WHERE {:s} id IN 
            (SELECT rowid FROM fts WHERE fts MATCH '{:s}: {:s}' ORDER BY RANK DESC)
            ORDER BY bibkey ASC
            """.format(genre_cond, all_fields, keyword)
        else:
            sql = """ SELECT bibkey FROM note WHERE {:s} id IN 
            (SELECT rowid FROM fts WHERE {:s} MATCH '{:s}' ORDER BY RANK DESC)
            ORDER BY bibkey ASC
            """.format(genre_cond, field, keyword)

    c.execute(sql)
    return list(res[0] for res in c.fetchall())


def db_search_bibkey(c, keyword, n_per_page, page=1):
    """ Query bibkeys that matches fields with keyword
    :argument
        c: sqlite3 cursor
        keyword: str            If empty, return all result
        n_per_page: int         number of entries per page (use LIMIT in SQL)
        page: int               take the "page"-th page (use OFFSET in SQL)
    :returns
        bibkeys: list of matched bibkeys
    """

    if keyword:
        sql = """ SELECT bibkey FROM note WHERE like('%{:s}%', bibkey)  
        ORDER BY bibkey ASC LIMIT {:d} OFFSET {:d} """.format(
                keyword, n_per_page, (page-1)*n_per_page)
    else:
        sql = """ SELECT bibkey FROM note ORDER BY bibkey ASC 
        LIMIT {:d} OFFSET {:d}""".format(n_per_page, (page-1)*n_per_page)
    c.execute(sql)
    return list(res[0] for res in c.fetchall())


def save_img_to_disk(img_pairs):
    """ Save image to disk
    :argument
        img_pairs:  [(link, QImage)]
    """

    for link, img in img_pairs:
        filename = path_join(ROOT, 'img', link)
        # check if this link is already on disk
        if isfile(filename):
            pass
        else:
            img.save(filename)


if __name__ == '__main__':

    launch()
